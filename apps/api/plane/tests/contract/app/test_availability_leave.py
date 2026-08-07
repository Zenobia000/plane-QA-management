# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Logging absences, and who gets to read why.

The redaction tests assert the field is **absent**, not empty. A key that is present with a
null value still tells a colleague there was a reason and invites a client to display a
placeholder; the point is that the reader learns nothing.
"""

from datetime import time

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import (
    LeaveStatus,
    LeaveType,
    MemberLeave,
    MemberWorkProfile,
    User,
    WorkCalendar,
    WorkspaceMember,
)

ADMIN = 20
MEMBER = 15

MON = "2026-08-03"
TUE = "2026-08-04"
WED = "2026-08-05"


def leaves_url(workspace):
    return f"/api/workspaces/{workspace.slug}/availability/leaves/"


def leave_detail_url(workspace, leave_id):
    return f"/api/workspaces/{workspace.slug}/availability/leaves/{leave_id}/"


def member_client(workspace, email, role=MEMBER):
    user = User.objects.create(email=email, username=email.split("@")[0])
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role, is_active=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return user, client


@pytest.fixture
def annual(db, workspace):
    return LeaveType.objects.create(workspace=workspace, name="Annual", requires_approval=True)


@pytest.fixture
def unpaid_no_approval(db, workspace):
    return LeaveType.objects.create(workspace=workspace, name="Remote", requires_approval=False)


@pytest.mark.contract
@pytest.mark.django_db
class TestLoggingLeave:
    def test_a_member_logs_their_own_absence(self, session_client, workspace, annual):
        response = session_client.post(
            leaves_url(workspace),
            {"leave_type": str(annual.id), "start_date": MON, "end_date": TUE, "reason": "family"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["status"] == LeaveStatus.PENDING

    def test_a_type_needing_no_approval_lands_approved(self, session_client, workspace, unpaid_no_approval):
        """No queue of requests that exist only to be rubber-stamped."""
        response = session_client.post(
            leaves_url(workspace),
            {"leave_type": str(unpaid_no_approval.id), "start_date": MON, "end_date": MON},
            format="json",
        )

        assert response.json()["status"] == LeaveStatus.APPROVED

    def test_a_half_day(self, session_client, workspace, annual):
        response = session_client.post(
            leaves_url(workspace),
            {
                "leave_type": str(annual.id),
                "start_date": MON,
                "end_date": MON,
                "start_day_part": "morning",
                "end_day_part": "morning",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_a_single_day_with_mismatched_halves_is_rejected(self, session_client, workspace, annual):
        response = session_client.post(
            leaves_url(workspace),
            {
                "leave_type": str(annual.id),
                "start_date": MON,
                "end_date": MON,
                "start_day_part": "morning",
                "end_day_part": "afternoon",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_a_multi_day_leave_cannot_start_in_the_morning(self, session_client, workspace, annual):
        # It would be a full first day; allowing both spellings gives two ways to say one
        # thing and a count that depends on which was used.
        response = session_client.post(
            leaves_url(workspace),
            {
                "leave_type": str(annual.id),
                "start_date": MON,
                "end_date": WED,
                "start_day_part": "morning",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_leave_that_ends_before_it_starts_is_rejected(self, session_client, workspace, annual):
        response = session_client.post(
            leaves_url(workspace),
            {"leave_type": str(annual.id), "start_date": WED, "end_date": MON},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_a_colleague_cannot_log_an_absence_for_someone_else(self, workspace, create_user, annual):
        _, client = member_client(workspace, "leave-colleague@plane.so")

        response = client.post(
            leaves_url(workspace),
            {
                "leave_type": str(annual.id),
                "start_date": MON,
                "end_date": MON,
                "member": str(create_user.id),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_an_admin_may_log_one_for_a_member(self, session_client, workspace, annual):
        member, _ = member_client(workspace, "leave-managed@plane.so")

        response = session_client.post(
            leaves_url(workspace),
            {"leave_type": str(annual.id), "start_date": MON, "end_date": MON, "member": str(member.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["member"] == str(member.id)

    def test_a_leave_type_from_another_workspace_is_rejected(self, session_client, workspace, create_user):
        from plane.db.models import Workspace

        elsewhere = Workspace.objects.create(name="Other", owner=create_user, slug="other-ws")
        foreign = LeaveType.objects.create(workspace=elsewhere, name="Annual")

        response = session_client.post(
            leaves_url(workspace),
            {"leave_type": str(foreign.id), "start_date": MON, "end_date": MON},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.contract
@pytest.mark.django_db
class TestReasonVisibility:
    @pytest.fixture
    def logged(self, workspace, create_user, annual):
        return MemberLeave.objects.create(
            workspace=workspace,
            member=create_user,
            leave_type=annual,
            start_date=MON,
            end_date=MON,
            reason="hospital appointment",
            status=LeaveStatus.APPROVED,
        )

    def _read(self, client, workspace):
        return client.get(leaves_url(workspace), {"from": MON, "to": WED}).json()[0]

    def test_the_member_sees_their_own_reason(self, session_client, workspace, logged):
        assert self._read(session_client, workspace)["reason"] == "hospital appointment"

    def test_a_colleague_sees_the_absence_but_not_the_reason(self, workspace, logged):
        _, client = member_client(workspace, "reason-peer@plane.so")

        row = self._read(client, workspace)

        assert row["start_date"] == MON
        assert row["leave_type"]
        # Absent, not null: a present key still says "there was a reason".
        assert "reason" not in row
        assert "decision_note" not in row

    def test_the_designated_approver_sees_it(self, workspace, create_user, logged):
        approver, client = member_client(workspace, "reason-approver@plane.so")
        MemberWorkProfile.objects.create(
            workspace=workspace,
            member=create_user,
            approver=approver,
            work_start_time=time(9, 0),
            work_end_time=time(18, 0),
        )

        assert self._read(client, workspace)["reason"] == "hospital appointment"

    def test_an_admin_sees_it(self, workspace, logged):
        _, client = member_client(workspace, "reason-admin@plane.so", role=ADMIN)

        assert self._read(client, workspace)["reason"] == "hospital appointment"


@pytest.mark.contract
@pytest.mark.django_db
class TestCancelling:
    @pytest.fixture
    def logged(self, workspace, create_user, annual):
        return MemberLeave.objects.create(
            workspace=workspace,
            member=create_user,
            leave_type=annual,
            start_date=MON,
            end_date=MON,
            status=LeaveStatus.APPROVED,
        )

    def test_a_member_cancels_their_own(self, session_client, workspace, logged):
        response = session_client.patch(
            leave_detail_url(workspace, logged.id), {"action": "cancel"}, format="json"
        )

        assert response.json()["status"] == LeaveStatus.CANCELLED

    def test_a_colleague_cannot(self, workspace, logged):
        _, client = member_client(workspace, "cancel-peer@plane.so")

        response = client.patch(leave_detail_url(workspace, logged.id), {"action": "cancel"}, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_a_cancelled_leave_leaves_the_default_list(self, session_client, workspace, logged):
        session_client.patch(leave_detail_url(workspace, logged.id), {"action": "cancel"}, format="json")

        assert session_client.get(leaves_url(workspace), {"from": MON, "to": WED}).json() == []
        # …but the row is still there, so history stays honest.
        assert (
            len(session_client.get(leaves_url(workspace), {"from": MON, "to": WED, "include_closed": "true"}).json())
            == 1
        )


@pytest.mark.contract
@pytest.mark.django_db
class TestAbsenceReachesTheSchedule:
    def test_an_approved_absence_removes_the_member_from_the_week(
        self, session_client, workspace, create_user, annual
    ):
        """One source of truth: away on the wallchart means away in the slot finder."""
        calendar = WorkCalendar.objects.create(
            workspace=workspace, name="Taiwan", timezone="Asia/Taipei", is_default=True
        )
        MemberWorkProfile.objects.create(
            workspace=workspace,
            member=create_user,
            work_calendar=calendar,
            work_start_time=time(9, 0),
            work_end_time=time(18, 0),
        )
        MemberLeave.objects.create(
            workspace=workspace,
            member=create_user,
            leave_type=annual,
            start_date=MON,
            end_date=MON,
            status=LeaveStatus.APPROVED,
        )

        body = session_client.get(
            f"/api/workspaces/{workspace.slug}/availability/schedule/", {"from": MON, "to": MON}
        ).json()

        member = next(m for m in body["members"] if m["member_id"] == str(create_user.id))
        assert member["working"] == []

    def test_a_morning_off_leaves_the_afternoon_reachable(
        self, session_client, workspace, create_user, annual
    ):
        calendar = WorkCalendar.objects.create(
            workspace=workspace, name="Taiwan", timezone="Asia/Taipei", is_default=True
        )
        MemberWorkProfile.objects.create(
            workspace=workspace,
            member=create_user,
            work_calendar=calendar,
            work_start_time=time(9, 0),
            work_end_time=time(18, 0),
        )
        MemberLeave.objects.create(
            workspace=workspace,
            member=create_user,
            leave_type=annual,
            start_date=MON,
            end_date=MON,
            start_day_part="morning",
            end_day_part="morning",
            status=LeaveStatus.APPROVED,
        )

        body = session_client.get(
            f"/api/workspaces/{workspace.slug}/availability/schedule/", {"from": MON, "to": MON}
        ).json()

        member = next(m for m in body["members"] if m["member_id"] == str(create_user.id))
        # 13:30-18:00 Taipei is 05:30-10:00 UTC.
        assert member["working"][0]["start"].startswith("2026-08-03T05:30:00")
        assert member["working"][0]["minutes"] == 270
