# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import Project, ProjectMember, User, WorkspaceMember


def _url(workspace, project):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/testing/capabilities/"


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(
        name="Testing Project",
        identifier="TST",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(
        workspace=workspace,
        project=project,
        member=create_user,
        role=20,
        is_active=True,
    )
    return project


@pytest.mark.contract
@pytest.mark.django_db
class TestTestingCapabilityEndpoint:
    def test_project_member_can_discover_capabilities(self, session_client, workspace, project):
        response = session_client.get(_url(workspace, project))

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "enabled": True,
            "stage": "manual-quality-loop",
            "capabilities": {
                "test_cases": True,
                "test_runs": True,
                "reports": True,
                "automation_ingestion": True,
            },
        }

    def test_anonymous_user_cannot_discover_capabilities(self, workspace, project):
        response = APIClient().get(_url(workspace, project))

        assert response.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}

    def test_non_project_member_cannot_discover_capabilities(self, workspace, project):
        outsider = User.objects.create(email="testing-outsider@plane.so", username="testing-outsider")
        WorkspaceMember.objects.create(workspace=workspace, member=outsider, role=15, is_active=True)
        client = APIClient()
        client.force_authenticate(user=outsider)

        response = client.get(_url(workspace, project))

        assert response.status_code == status.HTTP_403_FORBIDDEN
