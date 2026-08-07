# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Splitting one person across projects, and what a cycle is left with.

The sum-to-100 rule is blocked at the write rather than flagged in the UI, so the tests
that matter are the rejections. The capacity tests check that a day off costs a 50/50
member half a day on each project rather than a whole day on one — people do not take leave
from a project.
"""

from datetime import datetime, time, timezone as dt_timezone

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import (
    Cycle,
    LeaveStatus,
    LeaveType,
    MemberLeave,
    MemberWorkProfile,
    Project,
    ProjectMember,
    User,
    WorkCalendar,
    WorkspaceMember,
)

ADMIN = 20
MEMBER = 15


def allocations_url(workspace):
    return f"/api/workspaces/{workspace.slug}/availability/allocations/"


def capacity_url(workspace, project, cycle):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/cycles/{cycle.id}/capacity/"


def make_project(workspace, user, name, identifier):
    project = Project.objects.create(name=name, identifier=identifier, workspace=workspace, created_by=user)
    ProjectMember.objects.create(workspace=workspace, project=project, member=user, role=ADMIN, is_active=True)
    return project


@pytest.fixture
def alpha(db, workspace, create_user):
    return make_project(workspace, create_user, "Alpha", "ALP")


@pytest.fixture
def beta(db, workspace, create_user):
    return make_project(workspace, create_user, "Beta", "BET")


@pytest.fixture
def declared(db, workspace, create_user):
    calendar = WorkCalendar.objects.create(
        workspace=workspace, name="Taiwan", timezone="Asia/Taipei", is_default=True
    )
    return MemberWorkProfile.objects.create(
        workspace=workspace,
        member=create_user,
        work_calendar=calendar,
        work_start_time=time(9, 0),
        work_end_time=time(18, 0),
        hours_per_day=8,
    )


@pytest.fixture
def sprint(db, workspace, alpha, create_user):
    """Mon 2026-08-03 to Fri 2026-08-07: five working days."""
    return Cycle.objects.create(
        workspace=workspace,
        project=alpha,
        name="Sprint",
        start_date=datetime(2026, 8, 3, tzinfo=dt_timezone.utc),
        end_date=datetime(2026, 8, 7, tzinfo=dt_timezone.utc),
        owned_by=create_user,
    )


@pytest.mark.contract
@pytest.mark.django_db
class TestAllocationMatrix:
    def test_an_admin_allocates(self, session_client, workspace, create_user, alpha):
        response = session_client.put(
            allocations_url(workspace),
            {"member_id": str(create_user.id), "project_id": str(alpha.id), "allocation_percent": 50},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["allocation_percent"] == 50

    def test_two_halves_are_allowed(self, session_client, workspace, create_user, alpha, beta):
        for project in (alpha, beta):
            response = session_client.put(
                allocations_url(workspace),
                {"member_id": str(create_user.id), "project_id": str(project.id), "allocation_percent": 50},
                format="json",
            )
            assert response.status_code == status.HTTP_200_OK

        assert session_client.get(allocations_url(workspace)).json()["totals"][str(create_user.id)] == 100

    def test_over_allocation_is_refused_at_the_write(self, session_client, workspace, create_user, alpha, beta):
        """Not a warning label — two plans that cannot both be true."""
        session_client.put(
            allocations_url(workspace),
            {"member_id": str(create_user.id), "project_id": str(alpha.id), "allocation_percent": 60},
            format="json",
        )

        response = session_client.put(
            allocations_url(workspace),
            {"member_id": str(create_user.id), "project_id": str(beta.id), "allocation_percent": 60},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "120" in str(response.json()["error"])

    def test_raising_an_existing_allocation_counts_only_the_others(
        self, session_client, workspace, create_user, alpha, beta
    ):
        # Editing 50 -> 70 with 30 elsewhere is fine; naive summing would see 150.
        session_client.put(
            allocations_url(workspace),
            {"member_id": str(create_user.id), "project_id": str(alpha.id), "allocation_percent": 50},
            format="json",
        )
        session_client.put(
            allocations_url(workspace),
            {"member_id": str(create_user.id), "project_id": str(beta.id), "allocation_percent": 30},
            format="json",
        )

        response = session_client.put(
            allocations_url(workspace),
            {"member_id": str(create_user.id), "project_id": str(alpha.id), "allocation_percent": 70},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK

    def test_zero_removes_the_row_rather_than_storing_a_zero(
        self, session_client, workspace, create_user, alpha
    ):
        session_client.put(
            allocations_url(workspace),
            {"member_id": str(create_user.id), "project_id": str(alpha.id), "allocation_percent": 50},
            format="json",
        )

        session_client.put(
            allocations_url(workspace),
            {"member_id": str(create_user.id), "project_id": str(alpha.id), "allocation_percent": 0},
            format="json",
        )

        assert session_client.get(allocations_url(workspace)).json()["allocations"] == []

    def test_a_plain_member_cannot_allocate(self, workspace, create_user, alpha):
        user = User.objects.create(email="alloc-member@plane.so", username="alloc-member")
        WorkspaceMember.objects.create(workspace=workspace, member=user, role=MEMBER, is_active=True)
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.put(
            allocations_url(workspace),
            {"member_id": str(create_user.id), "project_id": str(alpha.id), "allocation_percent": 50},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.contract
@pytest.mark.django_db
class TestCycleCapacity:
    def test_a_full_time_member_has_every_working_hour(
        self, session_client, workspace, create_user, alpha, sprint, declared
    ):
        body = session_client.get(capacity_url(workspace, alpha, sprint)).json()

        assert body["ready"] is True
        row = body["members"][0]
        assert row["working_days"] == 5
        assert row["available_hours"] == 40.0

    def test_allocation_scales_the_hours(
        self, session_client, workspace, create_user, alpha, sprint, declared
    ):
        session_client.put(
            allocations_url(workspace),
            {"member_id": str(create_user.id), "project_id": str(alpha.id), "allocation_percent": 50},
            format="json",
        )

        body = session_client.get(capacity_url(workspace, alpha, sprint)).json()

        assert body["members"][0]["available_hours"] == 20.0

    def test_a_day_off_costs_a_half_time_member_half_a_day_here(
        self, session_client, workspace, create_user, alpha, sprint, declared
    ):
        """People do not take leave from a project — it reduces every project in proportion."""
        session_client.put(
            allocations_url(workspace),
            {"member_id": str(create_user.id), "project_id": str(alpha.id), "allocation_percent": 50},
            format="json",
        )
        annual = LeaveType.objects.create(workspace=workspace, name="Annual")
        MemberLeave.objects.create(
            workspace=workspace,
            member=create_user,
            leave_type=annual,
            start_date="2026-08-04",
            end_date="2026-08-04",
            status=LeaveStatus.APPROVED,
        )

        body = session_client.get(capacity_url(workspace, alpha, sprint)).json()

        # 5 days × 8h × 50% = 20h gross, minus one day's 8h × 50% = 4h.
        assert body["members"][0]["absence_hours"] == 4.0
        assert body["members"][0]["available_hours"] == 16.0

    def test_an_unallocated_project_assumes_full_time_and_says_so(
        self, session_client, workspace, alpha, sprint, declared
    ):
        """An empty panel on day one would make the feature look broken."""
        body = session_client.get(capacity_url(workspace, alpha, sprint)).json()

        assert body["allocation_is_assumed"] is True
        assert body["members"][0]["allocation_percent"] == 100

    def test_a_member_who_declared_no_hours_is_named(self, session_client, workspace, alpha, sprint):
        body = session_client.get(capacity_url(workspace, alpha, sprint)).json()

        assert body["members"][0]["available_hours"] == 0.0
        assert body["undeclared_members"] == [body["members"][0]["member_id"]]

    def test_a_points_project_gets_no_committed_comparison(
        self, session_client, workspace, alpha, sprint, declared
    ):
        """Points and hours are not commensurate; a ratio of the two reads like a fact."""
        body = session_client.get(capacity_url(workspace, alpha, sprint)).json()

        assert body["committed_comparable"] is False
        assert body["committed_hours"] is None

    def test_a_cycle_without_dates_says_so_instead_of_guessing(
        self, session_client, workspace, create_user, alpha, declared
    ):
        undated = Cycle.objects.create(
            workspace=workspace, project=alpha, name="Backlog", owned_by=create_user
        )

        body = session_client.get(capacity_url(workspace, alpha, undated)).json()

        assert body["ready"] is False
        assert body["reason"] == "cycle_has_no_dates"

    def test_a_holiday_inside_the_cycle_reduces_the_working_days(
        self, session_client, workspace, alpha, sprint, declared
    ):
        from plane.db.models import CalendarDay, CalendarDayKind

        CalendarDay.objects.create(
            workspace=workspace,
            calendar=declared.work_calendar,
            date="2026-08-05",
            name="Test holiday",
            kind=CalendarDayKind.HOLIDAY,
        )

        body = session_client.get(capacity_url(workspace, alpha, sprint)).json()

        assert body["members"][0]["working_days"] == 4
        assert body["members"][0]["available_hours"] == 32.0
