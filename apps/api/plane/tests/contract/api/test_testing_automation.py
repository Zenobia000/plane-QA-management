# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from rest_framework import status

from plane.db.models import Project, ProjectMember, TestAutomationIngestion, TestCaseAutomationLink, TestResult, TestRun


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(
        name="Automation Project", identifier="AUTO", workspace=workspace, created_by=create_user
    )
    ProjectMember.objects.create(
        workspace=workspace, project=project, member=create_user, role=20, is_active=True
    )
    return project


@pytest.mark.contract
@pytest.mark.django_db
class TestAutomationIngestionAPI:
    def url(self, workspace, project):
        return f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/testing/automation-ingestions/"

    def test_junit_ingestion_is_idempotent(self, api_key_client, workspace, project):
        payload = {
            "format": "junit",
            "source": "github-actions",
            "name": "CI 42",
            "build": "abc123",
            "junit_xml": '<testsuite><testcase classname="auth" name="login" time="0.1" />'
            '<testcase classname="auth" name="logout"><failure>HTTP 500</failure></testcase></testsuite>',
        }
        headers = {"HTTP_IDEMPOTENCY_KEY": "workflow-42"}
        created = api_key_client.post(self.url(workspace, project), payload, format="json", **headers)
        replayed = api_key_client.post(self.url(workspace, project), payload, format="json", **headers)

        assert created.status_code == status.HTTP_201_CREATED
        assert replayed.status_code == status.HTTP_200_OK
        assert replayed.json()["replayed"] is True
        assert replayed.json()["test_run"]["passed"] == 1
        assert replayed.json()["test_run"]["failed"] == 1
        assert TestRun.objects.filter(project=project).count() == 1
        assert TestResult.objects.filter(project=project).count() == 2
        assert TestCaseAutomationLink.objects.filter(project=project).count() == 2
        assert TestAutomationIngestion.objects.filter(project=project).count() == 1

    def test_reused_key_with_different_payload_conflicts(self, api_key_client, workspace, project):
        headers = {"HTTP_IDEMPOTENCY_KEY": "same-key"}
        base = {
            "name": "CI",
            "results": [{"external_id": "test-1", "status": "passed"}],
        }
        first = api_key_client.post(self.url(workspace, project), base, format="json", **headers)
        changed = {**base, "results": [{"external_id": "test-1", "status": "failed"}]}
        conflict = api_key_client.post(self.url(workspace, project), changed, format="json", **headers)
        assert first.status_code == status.HTTP_201_CREATED
        assert conflict.status_code == status.HTTP_409_CONFLICT

    def test_idempotency_header_is_required(self, api_key_client, workspace, project):
        response = api_key_client.post(
            self.url(workspace, project),
            {"name": "CI", "results": [{"external_id": "x", "status": "passed"}]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_app_and_public_adapters_share_idempotency(self, api_key_client, session_client, workspace, project):
        payload = {"name": "Shared command", "results": [{"external_id": "shared", "status": "passed"}]}
        headers = {"HTTP_IDEMPOTENCY_KEY": "shared-key"}
        app_url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/testing/automation-ingestions/"

        created = session_client.post(app_url, payload, format="json", **headers)
        replayed = api_key_client.post(self.url(workspace, project), payload, format="json", **headers)

        assert created.status_code == status.HTTP_201_CREATED
        assert replayed.status_code == status.HTTP_200_OK
        assert replayed.json()["id"] == created.json()["id"]
        assert replayed.json()["replayed"] is True
