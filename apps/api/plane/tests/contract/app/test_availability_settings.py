# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The settings paths a person actually has to walk.

These exist because the first cut of this module could create a work calendar but never
edit one, and could model a make-up workday but offer no way to enter it outside the seed
command. A feature nobody can reach through the product is not shipped.
"""

from datetime import time

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import (
    CalendarDay,
    CalendarDayKind,
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


def calendars_url(workspace):
    return f"/api/workspaces/{workspace.slug}/availability/calendars/"


def calendar_url(workspace, calendar):
    return f"{calendars_url(workspace)}{calendar.id}/"


def days_url(workspace, calendar):
    return f"{calendar_url(workspace, calendar)}days/"


def types_url(workspace):
    return f"/api/workspaces/{workspace.slug}/availability/leave-types/"


def member_client(workspace, email, role=MEMBER):
    user = User.objects.create(email=email, username=email.split("@")[0])
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role, is_active=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return user, client


@pytest.fixture
def taiwan(db, workspace):
    return WorkCalendar.objects.create(
        workspace=workspace, name="Taiwan", timezone="Asia/Taipei", is_default=True
    )


@pytest.mark.contract
@pytest.mark.django_db
class TestWorkCalendarEditing:
    def test_an_admin_renames_a_calendar(self, session_client, workspace, taiwan):
        response = session_client.patch(calendar_url(workspace, taiwan), {"name": "Taipei"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "Taipei"

    def test_an_admin_changes_the_working_week(self, session_client, workspace, taiwan):
        response = session_client.patch(
            calendar_url(workspace, taiwan), {"working_weekdays": [1, 2, 3, 4, 5, 6]}, format="json"
        )

        assert response.json()["working_weekdays"] == [1, 2, 3, 4, 5, 6]

    def test_an_empty_working_week_is_rejected(self, session_client, workspace, taiwan):
        response = session_client.patch(
            calendar_url(workspace, taiwan), {"working_weekdays": []}, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_promoting_a_new_default_demotes_the_old_one(self, session_client, workspace, taiwan):
        """One default, enforced by a partial-unique constraint — so the swap has to be atomic."""
        germany = WorkCalendar.objects.create(workspace=workspace, name="Germany", timezone="Europe/Berlin")

        response = session_client.patch(calendar_url(workspace, germany), {"is_default": True}, format="json")

        assert response.status_code == status.HTTP_200_OK
        taiwan.refresh_from_db()
        assert taiwan.is_default is False

    def test_a_plain_member_cannot_edit(self, workspace, taiwan):
        _, client = member_client(workspace, "cal-member@plane.so")

        assert (
            client.patch(calendar_url(workspace, taiwan), {"name": "Nope"}, format="json").status_code
            == status.HTTP_403_FORBIDDEN
        )

    def test_deleting_a_calendar_in_use_is_refused(self, session_client, workspace, create_user, taiwan):
        """Orphaning members onto the default would move their working days silently."""
        MemberWorkProfile.objects.create(
            workspace=workspace,
            member=create_user,
            work_calendar=taiwan,
            work_start_time=time(9, 0),
            work_end_time=time(18, 0),
        )

        response = session_client.delete(calendar_url(workspace, taiwan))

        assert response.status_code == status.HTTP_409_CONFLICT
        assert WorkCalendar.objects.filter(id=taiwan.id).exists()

    def test_an_unused_calendar_can_be_deleted(self, session_client, workspace, taiwan):
        assert session_client.delete(calendar_url(workspace, taiwan)).status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.contract
@pytest.mark.django_db
class TestCalendarDays:
    def test_an_admin_adds_a_holiday_and_a_makeup_workday(self, session_client, workspace, taiwan):
        """The path that did not exist. Without it `MAKEUP_WORKDAY` is unreachable by hand."""
        response = session_client.post(
            days_url(workspace, taiwan),
            {
                "days": [
                    {"date": "2026-02-28", "name": "和平紀念日", "kind": "holiday"},
                    {"date": "2026-02-27", "name": "補班", "kind": "makeup_workday"},
                ]
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert CalendarDay.objects.filter(calendar=taiwan).count() == 2
        assert CalendarDay.objects.filter(kind=CalendarDayKind.MAKEUP_WORKDAY).exists()

    def test_days_are_listed_and_filtered_by_year(self, session_client, workspace, taiwan):
        session_client.post(
            days_url(workspace, taiwan),
            {"days": [{"date": "2026-01-01", "name": "元旦", "kind": "holiday"}]},
            format="json",
        )
        session_client.post(
            days_url(workspace, taiwan),
            {"days": [{"date": "2027-01-01", "name": "元旦", "kind": "holiday"}]},
            format="json",
        )

        assert len(session_client.get(days_url(workspace, taiwan)).json()) == 2
        assert len(session_client.get(days_url(workspace, taiwan), {"year": "2026"}).json()) == 1

    def test_reimporting_a_year_replaces_it(self, session_client, workspace, taiwan):
        """What re-importing an officially revised list actually means."""
        session_client.post(
            days_url(workspace, taiwan),
            {"days": [{"date": "2026-04-04", "name": "Old", "kind": "holiday"}]},
            format="json",
        )

        session_client.post(
            days_url(workspace, taiwan),
            {
                "days": [{"date": "2026-04-05", "name": "Revised", "kind": "holiday"}],
                "replace_year": 2026,
            },
            format="json",
        )

        remaining = CalendarDay.objects.filter(calendar=taiwan)
        assert remaining.count() == 1
        assert remaining.first().name == "Revised"

    def test_posting_the_same_date_twice_updates_rather_than_duplicating(
        self, session_client, workspace, taiwan
    ):
        for name in ("First", "Second"):
            session_client.post(
                days_url(workspace, taiwan),
                {"days": [{"date": "2026-01-01", "name": name, "kind": "holiday"}]},
                format="json",
            )

        days = CalendarDay.objects.filter(calendar=taiwan)
        assert days.count() == 1
        assert days.first().name == "Second"

    def test_a_day_can_be_removed(self, session_client, workspace, taiwan):
        session_client.post(
            days_url(workspace, taiwan),
            {"days": [{"date": "2026-01-01", "name": "元旦", "kind": "holiday"}]},
            format="json",
        )
        day = CalendarDay.objects.get(calendar=taiwan)

        response = session_client.delete(f"{days_url(workspace, taiwan)}{day.id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not CalendarDay.objects.filter(id=day.id).exists()

    def test_a_plain_member_can_read_but_not_write(self, session_client, workspace, taiwan):
        session_client.post(
            days_url(workspace, taiwan),
            {"days": [{"date": "2026-01-01", "name": "元旦", "kind": "holiday"}]},
            format="json",
        )
        _, client = member_client(workspace, "days-member@plane.so")

        assert client.get(days_url(workspace, taiwan)).status_code == status.HTTP_200_OK
        assert (
            client.post(
                days_url(workspace, taiwan),
                {"days": [{"date": "2026-05-01", "name": "勞動節", "kind": "holiday"}]},
                format="json",
            ).status_code
            == status.HTTP_403_FORBIDDEN
        )

    def test_a_makeup_workday_actually_changes_the_schedule(
        self, session_client, workspace, create_user, taiwan
    ):
        """End to end: entering it in settings moves the week view.

        2026-02-28 is a Saturday. Marking it a make-up workday must make it a working day.
        """
        MemberWorkProfile.objects.create(
            workspace=workspace,
            member=create_user,
            work_calendar=taiwan,
            work_start_time=time(9, 0),
            work_end_time=time(18, 0),
        )
        url = f"/api/workspaces/{workspace.slug}/availability/schedule/"

        before = session_client.get(url, {"from": "2026-02-28", "to": "2026-02-28"}).json()
        assert next(m for m in before["members"] if m["member_id"] == str(create_user.id))["working"] == []

        session_client.post(
            days_url(workspace, taiwan),
            {"days": [{"date": "2026-02-28", "name": "補班", "kind": "makeup_workday"}]},
            format="json",
        )

        after = session_client.get(url, {"from": "2026-02-28", "to": "2026-02-28"}).json()
        assert next(m for m in after["members"] if m["member_id"] == str(create_user.id))["working"]


@pytest.mark.contract
@pytest.mark.django_db
class TestLeaveTypeEditing:
    @pytest.fixture
    def annual(self, workspace):
        return LeaveType.objects.create(workspace=workspace, name="Annual")

    def test_an_admin_renames_and_recolours(self, session_client, workspace, annual):
        response = session_client.patch(
            f"{types_url(workspace)}{annual.id}/", {"name": "特休", "colour": "#22C55E"}, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "特休"
        assert response.json()["colour"] == "#22C55E"

    def test_deactivating_keeps_the_absences_already_logged(
        self, session_client, workspace, create_user, annual
    ):
        """Retiring a type is not deleting it — the record of who was away stands."""
        MemberLeave.objects.create(
            workspace=workspace,
            member=create_user,
            leave_type=annual,
            start_date="2026-08-03",
            end_date="2026-08-03",
            status=LeaveStatus.APPROVED,
        )

        response = session_client.patch(
            f"{types_url(workspace)}{annual.id}/", {"is_active": False}, format="json"
        )

        assert response.json()["is_active"] is False
        assert MemberLeave.objects.filter(leave_type=annual).count() == 1

    def test_a_deactivated_type_cannot_be_used_for_a_new_absence(
        self, session_client, workspace, annual
    ):
        session_client.patch(f"{types_url(workspace)}{annual.id}/", {"is_active": False}, format="json")

        response = session_client.post(
            f"/api/workspaces/{workspace.slug}/availability/leaves/",
            {"leave_type": str(annual.id), "start_date": "2026-08-03", "end_date": "2026-08-03"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_a_plain_member_cannot_edit_a_type(self, workspace, annual):
        _, client = member_client(workspace, "type-member@plane.so")

        assert (
            client.patch(f"{types_url(workspace)}{annual.id}/", {"name": "Nope"}, format="json").status_code
            == status.HTTP_403_FORBIDDEN
        )
