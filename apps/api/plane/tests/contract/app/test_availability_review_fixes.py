# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Regressions for the defects an adversarial review of this branch turned up.

Each class is one finding. They are gathered here rather than filed into the per-surface
files because what they have in common is how they were found, and a later reader deciding
whether a guard is still needed benefits from seeing the failure it exists for.
"""

from datetime import datetime, time, timezone as dt_timezone

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from plane.availability import cancel_leave, may_decide, pending_for
from plane.db.models import (
    CalendarDay,
    CalendarDayKind,
    Cycle,
    Estimate,
    EstimatePoint,
    Issue,
    IssueType,
    LeaveStatus,
    LeaveType,
    MemberLeave,
    MemberProjectAllocation,
    MemberWorkProfile,
    Project,
    ProjectMember,
    State,
    User,
    WorkCalendar,
    Workspace,
    WorkspaceMember,
)

ADMIN = 20
MEMBER = 15
MON, FRI = "2026-08-03", "2026-08-07"


def add_member(workspace, email, role=MEMBER):
    user = User.objects.create(email=email, username=email.split("@")[0])
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role, is_active=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return user, client


def make_project(workspace, owner, name, identifier, members=()):
    project = Project.objects.create(name=name, identifier=identifier, workspace=workspace, created_by=owner)
    for member in members:
        ProjectMember.objects.create(
            workspace=workspace, project=project, member=member, role=ADMIN, is_active=True
        )
    return project


@pytest.mark.contract
@pytest.mark.django_db
class TestAllocationsAreScopedToVisibleProjects:
    """A workspace member must not learn a private project exists from the matrix."""

    def test_a_project_you_are_not_on_is_not_enumerated(self, workspace, create_user):
        secret = make_project(workspace, create_user, "Secret", "SEC", members=[create_user])
        MemberProjectAllocation.objects.create(
            workspace=workspace, member=create_user, project=secret, allocation_percent=40
        )
        _, outsider = add_member(workspace, "scope-outsider@plane.so")

        body = outsider.get(f"/api/workspaces/{workspace.slug}/availability/allocations/").json()

        assert body["allocations"] == []
        assert str(secret.id) not in outsider.get(
            f"/api/workspaces/{workspace.slug}/availability/allocations/"
        ).content.decode()

    def test_a_project_you_are_on_is_visible(self, workspace, create_user):
        member, client = add_member(workspace, "scope-insider@plane.so")
        shared = make_project(workspace, create_user, "Shared", "SHR", members=[create_user, member])
        MemberProjectAllocation.objects.create(
            workspace=workspace, member=create_user, project=shared, allocation_percent=40
        )

        body = client.get(f"/api/workspaces/{workspace.slug}/availability/allocations/").json()

        assert len(body["allocations"]) == 1

    def test_totals_still_count_projects_the_reader_cannot_see(self, workspace, create_user):
        """Otherwise a fully-booked colleague reads as free to whoever cannot see the rest."""
        member, client = add_member(workspace, "scope-total@plane.so")
        shared = make_project(workspace, create_user, "Shared", "SHR", members=[create_user, member])
        hidden = make_project(workspace, create_user, "Hidden", "HID", members=[create_user])
        for project, percent in ((shared, 40), (hidden, 60)):
            MemberProjectAllocation.objects.create(
                workspace=workspace, member=create_user, project=project, allocation_percent=percent
            )

        body = client.get(f"/api/workspaces/{workspace.slug}/availability/allocations/").json()

        assert len(body["allocations"]) == 1
        assert body["totals"][str(create_user.id)] == 100


@pytest.mark.contract
@pytest.mark.django_db
class TestPublicTreeMirrorsEveryRoute:
    """`docs/api/team-calendar.md` promises "two trees, same handlers"."""

    @pytest.mark.parametrize(
        "name",
        [
            "api-availability-calendar-detail",
            "api-availability-calendar-days",
            "api-availability-calendar-day-detail",
            "api-availability-leave-type-detail",
        ],
    )
    def test_the_route_is_registered(self, name):
        assert reverse(name, kwargs=_kwargs_for(name))

    def test_a_key_can_import_a_holiday_list(self, api_key_client, workspace):
        """The flow `seed_work_calendars` points operators at; it used to 404."""
        calendar = WorkCalendar.objects.create(
            workspace=workspace, name="Taiwan", timezone="Asia/Taipei", is_default=True
        )

        response = api_key_client.post(
            f"/api/v1/workspaces/{workspace.slug}/availability/calendars/{calendar.id}/days/",
            {"days": [{"date": "2026-02-27", "name": "補班", "kind": "makeup_workday"}]},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert CalendarDay.objects.filter(calendar=calendar, kind=CalendarDayKind.MAKEUP_WORKDAY).exists()


def _kwargs_for(name):
    base = {"slug": "s", "calendar_id": "00000000-0000-0000-0000-000000000001"}
    if name == "api-availability-calendar-day-detail":
        return {**base, "day_id": "00000000-0000-0000-0000-000000000002"}
    if name == "api-availability-leave-type-detail":
        return {"slug": "s", "type_id": "00000000-0000-0000-0000-000000000003"}
    if name == "api-availability-calendar-detail":
        return base
    return base


@pytest.mark.contract
@pytest.mark.django_db
class TestDeletingTheDefaultCalendar:
    def test_it_is_refused_while_anyone_relies_on_it_implicitly(self, session_client, workspace):
        """`work_calendar` is nullable and means "the default", so counting explicit
        assignments misses everyone who never chose one."""
        calendar = WorkCalendar.objects.create(
            workspace=workspace, name="Taiwan", timezone="Asia/Taipei", is_default=True
        )

        response = session_client.delete(
            f"/api/workspaces/{workspace.slug}/availability/calendars/{calendar.id}/"
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert WorkCalendar.objects.filter(id=calendar.id).exists()

    def test_a_non_default_calendar_with_no_users_still_deletes(self, session_client, workspace):
        WorkCalendar.objects.create(workspace=workspace, name="Default", timezone="UTC", is_default=True)
        spare = WorkCalendar.objects.create(workspace=workspace, name="Spare", timezone="Europe/Berlin")

        response = session_client.delete(
            f"/api/workspaces/{workspace.slug}/availability/calendars/{spare.id}/"
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.contract
@pytest.mark.django_db
class TestCancellingCannotRewriteADecision:
    @pytest.fixture
    def rejected(self, workspace, create_user):
        leave_type = LeaveType.objects.create(workspace=workspace, name="Annual")
        approver, _ = add_member(workspace, "cancel-approver@plane.so", role=ADMIN)
        return MemberLeave.objects.create(
            workspace=workspace,
            member=create_user,
            leave_type=leave_type,
            start_date=MON,
            end_date=MON,
            status=LeaveStatus.REJECTED,
            decided_by=approver,
            decided_at=datetime(2026, 8, 1, tzinfo=dt_timezone.utc),
            decision_note="we need you for the release",
        )

    def test_the_requester_cannot_cancel_a_rejected_leave(self, session_client, workspace, rejected):
        response = session_client.patch(
            f"/api/workspaces/{workspace.slug}/availability/leaves/{rejected.id}/",
            {"action": "cancel"},
            format="json",
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        rejected.refresh_from_db()
        assert rejected.status == LeaveStatus.REJECTED
        assert rejected.decision_note == "we need you for the release"

    def test_the_approver_of_record_is_preserved(self, workspace, create_user, rejected):
        original = rejected.decided_by_id

        from django.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            cancel_leave(leave_id=rejected.id, actor=create_user)

        rejected.refresh_from_db()
        assert rejected.decided_by_id == original

    def test_an_approved_leave_can_still_be_cancelled(self, session_client, workspace, create_user):
        leave_type = LeaveType.objects.create(workspace=workspace, name="Annual2")
        approved = MemberLeave.objects.create(
            workspace=workspace,
            member=create_user,
            leave_type=leave_type,
            start_date=MON,
            end_date=MON,
            status=LeaveStatus.APPROVED,
        )

        response = session_client.patch(
            f"/api/workspaces/{workspace.slug}/availability/leaves/{approved.id}/",
            {"action": "cancel"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.contract
@pytest.mark.django_db
class TestADeactivatedApproverDoesNotStrandARequest:
    @pytest.fixture
    def stranded(self, workspace, create_user):
        requester, _ = add_member(workspace, "strand-requester@plane.so")
        approver, _ = add_member(workspace, "strand-approver@plane.so")
        MemberWorkProfile.objects.create(
            workspace=workspace,
            member=requester,
            approver=approver,
            work_start_time=time(9, 0),
            work_end_time=time(18, 0),
        )
        leave = MemberLeave.objects.create(
            workspace=workspace,
            member=requester,
            leave_type=LeaveType.objects.create(workspace=workspace, name="Annual"),
            start_date=MON,
            end_date=MON,
            status=LeaveStatus.PENDING,
        )
        WorkspaceMember.objects.filter(workspace=workspace, member=approver).update(is_active=False)
        return leave

    def test_an_admin_regains_the_decision(self, workspace, create_user, stranded):
        assert may_decide(leave=stranded, actor=create_user) is True

    def test_the_request_reappears_in_the_admin_queue(self, workspace, create_user, stranded):
        assert stranded.id in {row.id for row in pending_for(workspace=workspace, actor=create_user)}

    def test_an_active_approver_still_owns_it_exclusively(self, workspace, create_user):
        requester, _ = add_member(workspace, "live-requester@plane.so")
        approver, _ = add_member(workspace, "live-approver@plane.so")
        MemberWorkProfile.objects.create(
            workspace=workspace,
            member=requester,
            approver=approver,
            work_start_time=time(9, 0),
            work_end_time=time(18, 0),
        )
        leave = MemberLeave.objects.create(
            workspace=workspace,
            member=requester,
            leave_type=LeaveType.objects.create(workspace=workspace, name="Annual"),
            start_date=MON,
            end_date=MON,
            status=LeaveStatus.PENDING,
        )

        assert may_decide(leave=leave, actor=approver) is True
        assert may_decide(leave=leave, actor=create_user) is False


@pytest.mark.contract
@pytest.mark.django_db
class TestClearingAProfileField:
    def _patch(self, client, workspace, member_id, payload):
        return client.patch(
            f"/api/workspaces/{workspace.slug}/availability/profiles/{member_id}/", payload, format="json"
        )

    def test_an_approver_can_be_withdrawn(self, session_client, workspace, create_user):
        approver, _ = add_member(workspace, "clear-approver@plane.so")
        self._patch(session_client, workspace, create_user.id, {"approver": str(approver.id)})

        body = self._patch(session_client, workspace, create_user.id, {"approver": None}).json()

        assert body["approver"] is None

    def test_a_calendar_can_be_returned_to_the_default(self, session_client, workspace, create_user):
        calendar = WorkCalendar.objects.create(workspace=workspace, name="Taiwan", timezone="Asia/Taipei")
        self._patch(session_client, workspace, create_user.id, {"work_calendar": str(calendar.id)})

        body = self._patch(session_client, workspace, create_user.id, {"work_calendar": None}).json()

        assert body["work_calendar"] is None

    def test_omitting_a_field_still_leaves_it_alone(self, session_client, workspace, create_user):
        approver, _ = add_member(workspace, "keep-approver@plane.so")
        self._patch(session_client, workspace, create_user.id, {"approver": str(approver.id)})

        body = self._patch(session_client, workspace, create_user.id, {"hours_per_day": "6.00"}).json()

        assert body["approver"] == str(approver.id)


@pytest.mark.contract
@pytest.mark.django_db
class TestOnLeaveIsNotUndeclared:
    def test_a_member_away_all_week_is_not_reported_as_having_no_hours(
        self, session_client, workspace, create_user
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
            leave_type=LeaveType.objects.create(workspace=workspace, name="Annual"),
            start_date=MON,
            end_date=FRI,
            status=LeaveStatus.APPROVED,
        )

        body = session_client.post(
            f"/api/workspaces/{workspace.slug}/availability/overlap/",
            {"member_ids": [str(create_user.id)], "date_from": MON, "date_to": FRI},
            format="json",
        ).json()

        assert body["working"] == []
        # Away, not silent. Reporting this as "hasn't declared any hours" sends the reader
        # off to fix a settings problem that does not exist.
        assert body["members_without_hours"] == []

    def test_a_member_with_no_profile_is_still_reported(self, session_client, workspace, create_user):
        body = session_client.post(
            f"/api/workspaces/{workspace.slug}/availability/overlap/",
            {"member_ids": [str(create_user.id)], "date_from": MON, "date_to": FRI},
            format="json",
        ).json()

        assert body["members_without_hours"] == [str(create_user.id)]


@pytest.mark.contract
@pytest.mark.django_db
class TestCommittedHours:
    @pytest.fixture
    def timed(self, workspace, create_user):
        project = make_project(workspace, create_user, "Alpha", "ALP", members=[create_user])
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
        estimate = Estimate.objects.create(
            workspace=workspace, project=project, name="Time", type="time", last_used=True
        )
        point = EstimatePoint.objects.create(
            workspace=workspace, project=project, estimate=estimate, key=1, value="8"
        )
        cycle = Cycle.objects.create(
            workspace=workspace,
            project=project,
            name="Sprint",
            start_date=datetime(2026, 8, 3, tzinfo=dt_timezone.utc),
            end_date=datetime(2026, 8, 7, tzinfo=dt_timezone.utc),
            owned_by=create_user,
        )
        state = State.objects.create(
            workspace=workspace, project=project, name="Doing", group="started", sequence=1000
        )
        return {"project": project, "cycle": cycle, "point": point, "state": state, "user": create_user}

    def _url(self, workspace, timed):
        return (
            f"/api/workspaces/{workspace.slug}/projects/{timed['project'].id}"
            f"/cycles/{timed['cycle'].id}/capacity/"
        )

    def _issue(self, workspace, timed, **kwargs):
        issue = Issue.objects.create(
            workspace=workspace,
            project=timed["project"],
            name="Work",
            state=timed["state"],
            estimate_point=timed["point"],
            created_by=timed["user"],
            **kwargs,
        )
        timed["cycle"].issue_cycle.create(
            workspace=workspace, project=timed["project"], issue=issue, created_by=timed["user"]
        )
        return issue

    def test_a_live_issue_counts(self, session_client, workspace, timed):
        self._issue(workspace, timed)

        assert session_client.get(self._url(workspace, timed)).json()["committed_hours"] == 8.0

    def test_an_issue_removed_from_the_cycle_stops_counting(self, session_client, workspace, timed):
        """Removing soft-deletes the CycleIssue row, which a join filter reads straight through."""
        issue = self._issue(workspace, timed)
        timed["cycle"].issue_cycle.filter(issue=issue).delete()

        assert session_client.get(self._url(workspace, timed)).json()["committed_hours"] == 0.0

    def test_a_draft_does_not_count(self, session_client, workspace, timed):
        self._issue(workspace, timed, is_draft=True)

        assert session_client.get(self._url(workspace, timed)).json()["committed_hours"] == 0.0

    def test_an_archived_issue_does_not_count(self, session_client, workspace, timed):
        self._issue(workspace, timed, archived_at=datetime(2026, 8, 4, tzinfo=dt_timezone.utc).date())

        assert session_client.get(self._url(workspace, timed)).json()["committed_hours"] == 0.0

    def test_a_non_finite_estimate_does_not_take_the_panel_down(self, session_client, workspace, timed):
        """`Decimal("nan")` parses happily and then raises three frames away in quantize()."""
        timed["point"].value = "NaN"
        timed["point"].save()
        self._issue(workspace, timed)

        response = session_client.get(self._url(workspace, timed))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["committed_hours"] == 0.0
