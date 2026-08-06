# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Team events, and defining a leave type, over HTTP.

`create_team_event` was covered at the service layer while the two endpoints in front of
it were not, so nothing asserted that an event could actually be created through the
product — only that the function it calls behaves. Same for defining a leave type: the
suite edited types it had built directly in the ORM, so the POST that a settings screen
sends was never exercised.
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import EventAudience, LeaveType, Project, TeamEvent, User, Workspace, WorkspaceMember

ADMIN = 20
MEMBER = 15


def events_url(workspace):
    return f"/api/workspaces/{workspace.slug}/availability/events/"


def types_url(workspace):
    return f"/api/workspaces/{workspace.slug}/availability/leave-types/"


def member_client(workspace, email, role=MEMBER):
    user = User.objects.create(email=email, username=email.split("@")[0])
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role, is_active=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return user, client


@pytest.fixture
def offsite(db, workspace):
    return TeamEvent.objects.create(
        workspace=workspace,
        title="Company offsite",
        start_date="2026-08-12",
        end_date="2026-08-14",
        colour="#8E24AA",
    )


@pytest.mark.contract
@pytest.mark.django_db
class TestTeamEventListing:
    def test_the_range_is_inclusive_at_both_ends(self, session_client, workspace, offsite):
        # An event running 12th-14th is part of the answer to "what is happening on the
        # 14th", and to "what is happening on the 12th".
        for day in ("2026-08-12", "2026-08-14"):
            response = session_client.get(events_url(workspace), {"from": day, "to": day})

            assert response.status_code == status.HTTP_200_OK
            assert [event["title"] for event in response.json()] == ["Company offsite"]

    def test_an_event_outside_the_window_is_left_out(self, session_client, workspace, offsite):
        response = session_client.get(events_url(workspace), {"from": "2026-09-01", "to": "2026-09-30"})

        assert response.json() == []

    def test_a_backwards_range_is_refused_rather_than_returning_nothing(self, session_client, workspace):
        # Silently returning an empty list would read as "nothing is happening", which is
        # a different answer from "that is not a range".
        response = session_client.get(events_url(workspace), {"from": "2026-08-14", "to": "2026-08-12"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_an_unparseable_date_is_refused(self, session_client, workspace):
        response = session_client.get(events_url(workspace), {"from": "last tuesday", "to": "2026-08-12"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_an_event_in_another_workspace_is_not_visible(self, session_client, workspace, offsite, create_user):
        other = Workspace.objects.create(name="Other", slug="other-co", owner=create_user)
        TeamEvent.objects.create(
            workspace=other, title="Their all-hands", start_date="2026-08-12", end_date="2026-08-12"
        )

        response = session_client.get(events_url(workspace), {"from": "2026-08-01", "to": "2026-08-31"})

        assert [event["title"] for event in response.json()] == ["Company offsite"]


@pytest.mark.contract
@pytest.mark.django_db
class TestTeamEventCreation:
    def test_an_admin_creates_an_all_members_event(self, session_client, workspace):
        response = session_client.post(
            events_url(workspace),
            {"title": "Company offsite", "start_date": "2026-08-12", "end_date": "2026-08-14"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["audience"] == EventAudience.ALL_MEMBERS
        # Declared, not inferred from an empty attendee list: "everyone" and "nobody yet"
        # must not share a spelling.
        assert response.json()["attendee_ids"] == []

    def test_a_selected_members_event_records_who_it_is_for(self, session_client, workspace):
        ana, _ = member_client(workspace, "ana@plane.so")

        response = session_client.post(
            events_url(workspace),
            {
                "title": "Release rehearsal",
                "start_date": "2026-08-12",
                "end_date": "2026-08-12",
                "audience": EventAudience.SELECTED_MEMBERS,
                "member_ids": [str(ana.id)],
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["attendee_ids"] == [str(ana.id)]

    def test_a_plain_member_cannot_create_one(self, workspace):
        _, client = member_client(workspace, "bob@plane.so")

        response = client.post(
            events_url(workspace),
            {"title": "Surprise all-hands", "start_date": "2026-08-12", "end_date": "2026-08-12"},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert TeamEvent.objects.count() == 0

    def test_a_project_from_another_workspace_is_refused(self, session_client, workspace, create_user):
        other = Workspace.objects.create(name="Other", slug="other-co-2", owner=create_user)
        theirs = Project.objects.create(workspace=other, name="Theirs", identifier="THR")

        response = session_client.post(
            events_url(workspace),
            {
                "title": "Their sprint review",
                "start_date": "2026-08-12",
                "end_date": "2026-08-12",
                "project": str(theirs.id),
            },
            format="json",
        )

        # Refused rather than quietly saved workspace-wide: an event attached to the wrong
        # project is a worse answer than no event.
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert TeamEvent.objects.count() == 0

    def test_a_backwards_event_is_refused(self, session_client, workspace):
        response = session_client.post(
            events_url(workspace),
            {"title": "Time travel", "start_date": "2026-08-14", "end_date": "2026-08-12"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_a_title_is_required(self, session_client, workspace):
        response = session_client.post(
            events_url(workspace), {"start_date": "2026-08-12", "end_date": "2026-08-12"}, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.contract
@pytest.mark.django_db
class TestLeaveTypeCreation:
    def test_an_admin_defines_a_leave_type(self, session_client, workspace):
        response = session_client.post(
            types_url(workspace),
            {"name": "特休", "colour": "#22C55E", "consumes_capacity": True, "requires_approval": True},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["name"] == "特休"
        # Names are user data, not an enum: a workspace that runs in Chinese should not
        # have to pick from an English list.
        assert LeaveType.objects.get(workspace=workspace).name == "特休"

    def test_a_plain_member_cannot_define_one(self, workspace):
        _, client = member_client(workspace, "bob@plane.so")

        response = client.post(types_url(workspace), {"name": "Unlimited PTO"}, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert LeaveType.objects.count() == 0

    def test_a_nameless_type_is_refused(self, session_client, workspace):
        response = session_client.post(types_url(workspace), {"colour": "#22C55E"}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_a_duplicate_name_is_refused(self, session_client, workspace):
        LeaveType.objects.create(workspace=workspace, name="Annual")

        response = session_client.post(types_url(workspace), {"name": "Annual"}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert LeaveType.objects.filter(name="Annual").count() == 1

    def test_the_same_name_is_allowed_in_a_different_workspace(self, session_client, workspace, create_user):
        other = Workspace.objects.create(name="Other", slug="other-co-3", owner=create_user)
        LeaveType.objects.create(workspace=other, name="Annual")

        response = session_client.post(types_url(workspace), {"name": "Annual"}, format="json")

        assert response.status_code == status.HTTP_201_CREATED

    def test_every_member_can_read_the_list(self, workspace):
        LeaveType.objects.create(workspace=workspace, name="Annual")
        _, client = member_client(workspace, "bob@plane.so")

        response = client.get(types_url(workspace))

        # Readable by everyone on purpose: somebody about to book time off needs to know
        # what they are allowed to book.
        assert response.status_code == status.HTTP_200_OK
        assert [entry["name"] for entry in response.json()] == ["Annual"]


@pytest.mark.contract
@pytest.mark.django_db
class TestWorkCalendarCreation:
    """The other settings POST the suite never sent.

    Every existing case built its calendar in the ORM, so the endpoint a settings screen
    actually posts to was reached only by the tests that edit one afterwards.
    """

    def calendars_url(self, workspace):
        return f"/api/workspaces/{workspace.slug}/availability/calendars/"

    def test_an_admin_creates_a_calendar(self, session_client, workspace):
        response = session_client.post(
            self.calendars_url(workspace),
            {"name": "Taiwan", "timezone": "Asia/Taipei", "working_weekdays": [1, 2, 3, 4, 5]},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["timezone"] == "Asia/Taipei"

    def test_a_plain_member_cannot_create_one(self, workspace):
        _, client = member_client(workspace, "bob@plane.so")

        response = client.post(self.calendars_url(workspace), {"name": "Mine"}, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_an_unknown_timezone_is_refused(self, session_client, workspace):
        # A calendar in a zone Python cannot resolve produces no working hours at all, and
        # the member bound to it silently disappears from every week view.
        response = session_client.post(
            self.calendars_url(workspace), {"name": "Nowhere", "timezone": "Mars/Olympus"}, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_a_week_with_no_working_days_is_refused(self, session_client, workspace):
        response = session_client.post(
            self.calendars_url(workspace),
            {"name": "Permanent weekend", "timezone": "Asia/Taipei", "working_weekdays": []},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_every_member_can_read_the_calendars(self, session_client, workspace):
        session_client.post(
            self.calendars_url(workspace), {"name": "Taiwan", "timezone": "Asia/Taipei"}, format="json"
        )
        _, client = member_client(workspace, "bob@plane.so")

        response = client.get(self.calendars_url(workspace))

        assert response.status_code == status.HTTP_200_OK
        assert [entry["name"] for entry in response.json()] == ["Taiwan"]


@pytest.mark.contract
@pytest.mark.django_db
class TestApproverMustBeReachable:
    def profile_url(self, workspace, member):
        return f"/api/workspaces/{workspace.slug}/availability/profiles/{member.id}/"

    def test_an_approver_outside_the_workspace_is_refused(self, session_client, workspace):
        outsider = User.objects.create(email="outsider@elsewhere.so", username="outsider")
        ana, _ = member_client(workspace, "ana@plane.so")

        response = session_client.patch(
            self.profile_url(workspace, ana), {"approver": str(outsider.id)}, format="json"
        )

        # A pointer at somebody who cannot act on the request is a dead end, not a setting:
        # the leave would sit pending with nobody able to decide it.
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_an_approver_inside_the_workspace_is_accepted(self, session_client, workspace):
        ana, _ = member_client(workspace, "ana@plane.so")
        lead, _ = member_client(workspace, "lead@plane.so")

        response = session_client.patch(
            self.profile_url(workspace, ana), {"approver": str(lead.id)}, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["approver"] == str(lead.id)

    def test_a_member_who_has_declared_nothing_reads_as_undeclared(self, session_client, workspace):
        ana, _ = member_client(workspace, "ana@plane.so")

        response = session_client.get(self.profile_url(workspace, ana))

        # Not a 404: "this person has not said" is an answer the week view needs to draw.
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["declared"] is False

    def test_hours_cannot_be_set_for_somebody_outside_the_workspace(self, session_client, workspace):
        outsider = User.objects.create(email="outsider2@elsewhere.so", username="outsider2")

        response = session_client.patch(
            self.profile_url(workspace, outsider), {"hours_per_day": 8}, format="json"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_a_member_cannot_set_somebody_else_hours(self, workspace):
        ana, _ = member_client(workspace, "ana@plane.so")
        _, bobs_client = member_client(workspace, "bob@plane.so")

        response = bobs_client.patch(self.profile_url(workspace, ana), {"hours_per_day": 4}, format="json")

        # Declaring your working hours is a statement about yourself. A colleague editing
        # it turns a declaration into an assignment.
        assert response.status_code == status.HTTP_403_FORBIDDEN
