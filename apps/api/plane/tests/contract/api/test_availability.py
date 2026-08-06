# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The API-key mirror.

These endpoints are thin subclasses of the app-tree ones, so the behaviour is covered
there. What needs asserting here is the boundary: that a key reaches them at all, that a
missing key does not, and that failures come back in the public error envelope rather than
in whatever shape DRF happened to produce.
"""

from datetime import time

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import MemberWorkProfile, WorkCalendar, WorkspaceMember


def url(workspace, suffix):
    return f"/api/v1/workspaces/{workspace.slug}/availability/{suffix}"


@pytest.fixture
def declared(db, workspace, create_user):
    WorkspaceMember.objects.get_or_create(
        workspace=workspace, member=create_user, defaults={"role": 20, "is_active": True}
    )
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
    return calendar


@pytest.mark.contract
@pytest.mark.django_db
class TestAvailabilityPublicAPI:
    def test_a_key_reads_the_schedule(self, api_key_client, workspace, declared):
        response = api_key_client.get(url(workspace, "schedule/"), {"from": "2026-08-03", "to": "2026-08-03"})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["members"][0]["working"][0]["start"].startswith("2026-08-03T01:00:00")

    def test_a_key_finds_an_overlap(self, api_key_client, workspace, create_user, declared):
        response = api_key_client.post(
            url(workspace, "overlap/"),
            {
                "member_ids": [str(create_user.id)],
                "date_from": "2026-08-03",
                "date_to": "2026-08-03",
                "duration_minutes": 60,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["working"][0]["minutes"] == 540

    def test_a_key_lists_calendars(self, api_key_client, workspace, declared):
        response = api_key_client.get(url(workspace, "calendars/"))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()[0]["timezone"] == "Asia/Taipei"

    def test_no_key_is_refused(self, workspace, declared):
        response = APIClient().get(url(workspace, "schedule/"), {"from": "2026-08-03", "to": "2026-08-03"})

        assert response.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}

    def test_a_bad_request_comes_back_in_the_public_error_envelope(self, api_key_client, workspace, declared):
        response = api_key_client.get(url(workspace, "schedule/"))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        body = response.json()
        assert "error" in body
        assert body["error"]["code"] == "http_400"
        assert body["error"]["request_id"]

    def test_every_response_carries_a_request_id(self, api_key_client, workspace, declared):
        response = api_key_client.get(url(workspace, "capabilities/"))

        assert response["X-Request-ID"]

    def test_no_payload_reports_observed_activity(self, api_key_client, workspace, declared):
        body = api_key_client.get(
            url(workspace, "schedule/"), {"from": "2026-08-03", "to": "2026-08-07"}
        ).content.decode()

        assert "last_active" not in body
