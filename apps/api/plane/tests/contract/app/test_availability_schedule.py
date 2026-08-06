# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The schedule, overlap and profile endpoints over real rows.

The end-to-end case worth having is two members in different cities: it exercises the
calendar, the profile, the zone resolution and the intersection in one request, and it is
the question the surface exists to answer.
"""

from datetime import time

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import MemberWorkProfile, User, WorkCalendar, WorkspaceMember

ADMIN = 20
MEMBER = 15
GUEST = 5

MONDAY = "2026-08-03"
FRIDAY = "2026-08-07"


def schedule_url(workspace):
    return f"/api/workspaces/{workspace.slug}/availability/schedule/"


def overlap_url(workspace):
    return f"/api/workspaces/{workspace.slug}/availability/overlap/"


def profile_url(workspace, member_id):
    return f"/api/workspaces/{workspace.slug}/availability/profiles/{member_id}/"


@pytest.fixture
def taipei(db, workspace):
    return WorkCalendar.objects.create(
        workspace=workspace, name="Taiwan", timezone="Asia/Taipei", is_default=True
    )


@pytest.fixture
def berlin(db, workspace):
    return WorkCalendar.objects.create(workspace=workspace, name="Germany", timezone="Europe/Berlin")


def add_member(workspace, email, role=MEMBER):
    user = User.objects.create(email=email, username=email.split("@")[0])
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role, is_active=True)
    return user


def declare(workspace, member, calendar, start=time(9, 0), end=time(18, 0), core=None):
    return MemberWorkProfile.objects.create(
        workspace=workspace,
        member=member,
        work_calendar=calendar,
        work_start_time=start,
        work_end_time=end,
        core_hours_start=core[0] if core else None,
        core_hours_end=core[1] if core else None,
    )


@pytest.mark.contract
@pytest.mark.django_db
class TestSchedule:
    def test_a_range_is_required(self, session_client, workspace):
        response = session_client.get(schedule_url(workspace))

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_an_inverted_range_is_rejected(self, session_client, workspace):
        response = session_client.get(schedule_url(workspace), {"from": FRIDAY, "to": MONDAY})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_an_absurd_range_is_rejected_rather_than_paged(self, session_client, workspace):
        response = session_client.get(schedule_url(workspace), {"from": "2020-01-01", "to": "2030-01-01"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_a_malformed_date_is_rejected(self, session_client, workspace):
        response = session_client.get(schedule_url(workspace), {"from": "03-08-2026", "to": FRIDAY})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_local_hours_come_back_as_utc_instants(self, session_client, workspace, create_user, taipei):
        declare(workspace, create_user, taipei)

        body = session_client.get(schedule_url(workspace), {"from": MONDAY, "to": MONDAY}).json()

        member = next(m for m in body["members"] if m["member_id"] == str(create_user.id))
        assert member["timezone"] == "Asia/Taipei"
        assert member["working"][0]["start"].startswith("2026-08-03T01:00:00")
        assert member["working"][0]["minutes"] == 540

    def test_a_member_who_declared_nothing_appears_with_no_windows(
        self, session_client, workspace, create_user, taipei
    ):
        body = session_client.get(schedule_url(workspace), {"from": MONDAY, "to": MONDAY}).json()

        member = next(m for m in body["members"] if m["member_id"] == str(create_user.id))
        assert member["working"] == []

    def test_a_guest_cannot_read_the_team_schedule(self, workspace, taipei):
        guest = add_member(workspace, "sched-guest@plane.so", role=GUEST)
        client = APIClient()
        client.force_authenticate(user=guest)

        response = client.get(schedule_url(workspace), {"from": MONDAY, "to": MONDAY})

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_no_payload_reports_observed_activity(self, session_client, workspace, create_user, taipei):
        """ADR 0008 bars this surface from `last_active`. Asserted, not merely intended."""
        declare(workspace, create_user, taipei)

        body = session_client.get(schedule_url(workspace), {"from": MONDAY, "to": FRIDAY}).content.decode()

        assert "last_active" not in body
        assert "last_login" not in body


@pytest.mark.contract
@pytest.mark.django_db
class TestOverlap:
    def test_taipei_and_berlin_share_three_hours(self, session_client, workspace, create_user, taipei, berlin):
        declare(workspace, create_user, taipei)
        colleague = add_member(workspace, "overlap-berlin@plane.so")
        declare(workspace, colleague, berlin)

        response = session_client.post(
            overlap_url(workspace),
            {
                "member_ids": [str(create_user.id), str(colleague.id)],
                "date_from": MONDAY,
                "date_to": MONDAY,
                "duration_minutes": 60,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        working = response.json()["working"]
        assert len(working) == 1
        assert working[0]["minutes"] == 180
        assert working[0]["start"].startswith("2026-08-03T07:00:00")

    def test_a_duration_longer_than_the_shared_stretch_returns_nothing(
        self, session_client, workspace, create_user, taipei, berlin
    ):
        declare(workspace, create_user, taipei)
        colleague = add_member(workspace, "overlap-long@plane.so")
        declare(workspace, colleague, berlin)

        response = session_client.post(
            overlap_url(workspace),
            {
                "member_ids": [str(create_user.id), str(colleague.id)],
                "date_from": MONDAY,
                "date_to": MONDAY,
                "duration_minutes": 240,
            },
            format="json",
        )

        assert response.json()["working"] == []

    def test_a_member_without_declared_hours_is_named_rather_than_silently_emptying_the_result(
        self, session_client, workspace, create_user, taipei
    ):
        declare(workspace, create_user, taipei)
        silent = add_member(workspace, "overlap-silent@plane.so")

        body = session_client.post(
            overlap_url(workspace),
            {
                "member_ids": [str(create_user.id), str(silent.id)],
                "date_from": MONDAY,
                "date_to": MONDAY,
            },
            format="json",
        ).json()

        assert body["working"] == []
        assert str(silent.id) in body["members_without_hours"]

    def test_an_empty_member_list_is_rejected(self, session_client, workspace):
        response = session_client.post(
            overlap_url(workspace),
            {"member_ids": [], "date_from": MONDAY, "date_to": MONDAY},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.contract
@pytest.mark.django_db
class TestWorkProfile:
    def test_a_member_declares_their_own_hours(self, session_client, workspace, create_user, taipei):
        response = session_client.patch(
            profile_url(workspace, create_user.id),
            {"work_start_time": "10:00", "work_end_time": "19:00", "work_calendar": str(taipei.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["work_start_time"] == "10:00:00"

    def test_a_colleague_cannot_declare_hours_on_someone_else_behalf(self, workspace, create_user, taipei):
        other = add_member(workspace, "profile-other@plane.so")
        client = APIClient()
        client.force_authenticate(user=other)

        response = client.patch(
            profile_url(workspace, create_user.id),
            {"work_start_time": "06:00"},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_an_admin_may_set_hours_for_a_member(self, session_client, workspace, taipei):
        member = add_member(workspace, "profile-managed@plane.so")

        response = session_client.patch(
            profile_url(workspace, member.id), {"hours_per_day": "6.00"}, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["hours_per_day"] == "6.00"

    def test_a_working_day_that_ends_before_it_starts_is_rejected(self, session_client, workspace, create_user):
        response = session_client.patch(
            profile_url(workspace, create_user.id),
            {"work_start_time": "18:00", "work_end_time": "09:00"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_core_hours_outside_the_working_window_are_rejected(self, session_client, workspace, create_user):
        response = session_client.patch(
            profile_url(workspace, create_user.id),
            {"core_hours_start": "07:00", "core_hours_end": "08:00"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_core_hours_can_be_withdrawn(self, session_client, workspace, create_user):
        session_client.patch(
            profile_url(workspace, create_user.id),
            {"core_hours_start": "14:00", "core_hours_end": "17:00"},
            format="json",
        )

        response = session_client.patch(
            profile_url(workspace, create_user.id), {"clear_core_hours": True}, format="json"
        )

        assert response.json()["core_hours_start"] is None

    def test_a_calendar_from_another_workspace_is_rejected(self, session_client, workspace, create_user, db):
        from plane.db.models import Workspace

        elsewhere = Workspace.objects.create(name="Other", owner=create_user, slug="other-workspace")
        foreign = WorkCalendar.objects.create(workspace=elsewhere, name="Foreign", timezone="UTC")

        response = session_client.patch(
            profile_url(workspace, create_user.id),
            {"work_calendar": str(foreign.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_an_undeclared_profile_reads_as_undeclared_rather_than_404(
        self, session_client, workspace, create_user
    ):
        response = session_client.get(profile_url(workspace, create_user.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["declared"] is False
