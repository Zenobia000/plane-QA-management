# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Who can reach the team calendar, and what it admits to supporting.

The guest case is the one worth having. Availability is the only workspace surface in this
fork that a guest may not read, and the rule lives in a permission class of its own
precisely because the obvious choice -- `WorkspaceEntityPermission` -- would have let them
in on every safe method without anyone noticing.
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import User, WorkspaceMember

ADMIN = 20
MEMBER = 15
GUEST = 5


def _url(workspace):
    return f"/api/workspaces/{workspace.slug}/availability/capabilities/"


def _client_for(workspace, role, email):
    user = User.objects.create(email=email, username=email.split("@")[0])
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role, is_active=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.contract
@pytest.mark.django_db
class TestAvailabilityCapabilityEndpoint:
    def test_workspace_admin_can_discover_capabilities(self, session_client, workspace):
        response = session_client.get(_url(workspace))

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "enabled": True,
            "stage": "allocation-and-capacity",
            "capabilities": {
                "schedule": True,
                "overlap": True,
                "leave": True,
                "allocation": True,
                "capacity": True,
            },
        }

    def test_workspace_member_can_discover_capabilities(self, workspace):
        client = _client_for(workspace, MEMBER, "availability-member@plane.so")

        assert client.get(_url(workspace)).status_code == status.HTTP_200_OK

    def test_guest_cannot_discover_capabilities(self, workspace):
        """A guest is someone let into one project, not a member of the team."""
        client = _client_for(workspace, GUEST, "availability-guest@plane.so")

        assert client.get(_url(workspace)).status_code == status.HTTP_403_FORBIDDEN

    def test_deactivated_member_cannot_discover_capabilities(self, workspace):
        user = User.objects.create(email="availability-former@plane.so", username="availability-former")
        WorkspaceMember.objects.create(workspace=workspace, member=user, role=ADMIN, is_active=False)
        client = APIClient()
        client.force_authenticate(user=user)

        assert client.get(_url(workspace)).status_code == status.HTTP_403_FORBIDDEN

    def test_anonymous_user_cannot_discover_capabilities(self, workspace):
        response = APIClient().get(_url(workspace))

        assert response.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}

    def test_non_member_cannot_discover_capabilities(self, workspace):
        outsider = User.objects.create(email="availability-outsider@plane.so", username="availability-outsider")
        client = APIClient()
        client.force_authenticate(user=outsider)

        assert client.get(_url(workspace)).status_code == status.HTTP_403_FORBIDDEN

    def test_no_response_field_reports_observed_activity(self, session_client, workspace):
        """ADR 0008: availability is declared, never observed.

        `User.last_active` exists on the model and is the cheapest way to answer "is anyone
        around" -- which is exactly why this module is barred from surfacing it. Asserted
        here so the prohibition fails a test rather than a code review.
        """
        body = session_client.get(_url(workspace)).content.decode()

        assert "last_active" not in body
        assert "last_login" not in body
