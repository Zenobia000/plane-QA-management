# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Deciding a request.

Plane has no reporting line, so "who approves this" is a pointer per member with a fallback
to any workspace admin. The tests that matter are the ones about who may *not* decide: the
requester themself, and an admin whose colleague named someone else.
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
    WorkspaceMember,
)

ADMIN = 20
MEMBER = 15
MON = "2026-08-03"


def detail_url(workspace, leave_id):
    return f"/api/workspaces/{workspace.slug}/availability/leaves/{leave_id}/"


def pending_url(workspace):
    return f"/api/workspaces/{workspace.slug}/availability/leaves/pending/"


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
def requester(db, workspace, annual):
    user, client = member_client(workspace, "approval-requester@plane.so")
    leave = MemberLeave.objects.create(
        workspace=workspace,
        member=user,
        leave_type=annual,
        start_date=MON,
        end_date=MON,
        reason="wedding",
        status=LeaveStatus.PENDING,
    )
    return user, client, leave


@pytest.mark.contract
@pytest.mark.django_db
class TestDeciding:
    def test_an_admin_approves_when_no_approver_is_named(self, session_client, workspace, requester):
        _, _, leave = requester

        response = session_client.patch(detail_url(workspace, leave.id), {"action": "approve"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == LeaveStatus.APPROVED

    def test_an_admin_rejects_with_a_note(self, session_client, workspace, requester):
        _, _, leave = requester

        response = session_client.patch(
            detail_url(workspace, leave.id), {"action": "reject", "note": "release week"}, format="json"
        )

        assert response.json()["status"] == LeaveStatus.REJECTED
        assert response.json()["decision_note"] == "release week"

    def test_the_named_approver_decides_instead_of_an_admin(self, session_client, workspace, requester):
        """A pointer per member is how "my manager decides" is said without an org chart."""
        member, _, leave = requester
        approver, approver_client = member_client(workspace, "approval-named@plane.so")
        MemberWorkProfile.objects.create(
            workspace=workspace,
            member=member,
            approver=approver,
            work_start_time=time(9, 0),
            work_end_time=time(18, 0),
        )

        # The admin is no longer the one on the hook.
        assert (
            session_client.patch(detail_url(workspace, leave.id), {"action": "approve"}, format="json").status_code
            == status.HTTP_403_FORBIDDEN
        )
        assert (
            approver_client.patch(
                detail_url(workspace, leave.id), {"action": "approve"}, format="json"
            ).status_code
            == status.HTTP_200_OK
        )

    def test_nobody_approves_their_own_request(self, workspace, requester):
        """Even an admin. Self-approval is not approval."""
        member, client, leave = requester
        WorkspaceMember.objects.filter(workspace=workspace, member=member).update(role=ADMIN)

        response = client.patch(detail_url(workspace, leave.id), {"action": "approve"}, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_a_plain_colleague_cannot_decide(self, workspace, requester):
        _, _, leave = requester
        _, client = member_client(workspace, "approval-bystander@plane.so")

        response = client.patch(detail_url(workspace, leave.id), {"action": "approve"}, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_deciding_twice_conflicts_rather_than_overwriting(self, session_client, workspace, requester):
        """Two approvers clicking at once must not have the second silently win."""
        _, _, leave = requester
        session_client.patch(detail_url(workspace, leave.id), {"action": "approve"}, format="json")

        second = session_client.patch(detail_url(workspace, leave.id), {"action": "reject"}, format="json")

        assert second.status_code == status.HTTP_409_CONFLICT
        leave.refresh_from_db()
        assert leave.status == LeaveStatus.APPROVED

    def test_an_unknown_action_is_rejected(self, session_client, workspace, requester):
        _, _, leave = requester

        response = session_client.patch(detail_url(workspace, leave.id), {"action": "shred"}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_approving_makes_the_absence_bind(self, session_client, workspace, requester):
        member, _, leave = requester

        before = session_client.get(
            f"/api/workspaces/{workspace.slug}/availability/schedule/", {"from": MON, "to": MON}
        ).json()
        session_client.patch(detail_url(workspace, leave.id), {"action": "approve"}, format="json")
        after = session_client.get(
            f"/api/workspaces/{workspace.slug}/availability/schedule/", {"from": MON, "to": MON}
        ).json()

        assert before is not None and after is not None
        entry = next(m for m in after["members"] if m["member_id"] == str(member.id))
        assert entry["working"] == []


@pytest.mark.contract
@pytest.mark.django_db
class TestPendingQueue:
    def test_an_admin_sees_requests_with_no_named_approver(self, session_client, workspace, requester):
        """Otherwise a workspace where nobody set an approver has a queue nobody can see."""
        assert len(session_client.get(pending_url(workspace)).json()) == 1

    def test_an_admin_stops_seeing_it_once_someone_else_is_named(self, session_client, workspace, requester):
        member, _, _ = requester
        approver, approver_client = member_client(workspace, "queue-named@plane.so")
        MemberWorkProfile.objects.create(
            workspace=workspace,
            member=member,
            approver=approver,
            work_start_time=time(9, 0),
            work_end_time=time(18, 0),
        )

        assert session_client.get(pending_url(workspace)).json() == []
        assert len(approver_client.get(pending_url(workspace)).json()) == 1

    def test_nobody_sees_their_own_request_in_their_queue(self, workspace, requester):
        _, client, _ = requester

        assert client.get(pending_url(workspace)).json() == []

    def test_the_queue_shows_the_reason_to_whoever_must_decide(self, session_client, workspace, requester):
        assert session_client.get(pending_url(workspace)).json()[0]["reason"] == "wedding"

    def test_a_decided_request_leaves_the_queue(self, session_client, workspace, requester):
        _, _, leave = requester
        session_client.patch(detail_url(workspace, leave.id), {"action": "approve"}, format="json")

        assert session_client.get(pending_url(workspace)).json() == []
