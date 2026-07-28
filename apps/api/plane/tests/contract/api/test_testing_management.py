# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import APIToken, Issue, Project, ProjectMember, TestCase, TestFolder, TestResult, User


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(
        name="Agent Managed QA",
        identifier="AMQA",
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


def _base(workspace, project):
    return f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/testing"


@pytest.mark.contract
@pytest.mark.django_db
class TestPublicTestingManagementAPI:
    def test_api_key_can_complete_library_and_run_lifecycle(self, api_key_client, workspace, project):
        base = _base(workspace, project)
        capability = api_key_client.get(f"{base}/capabilities/")
        assert capability.status_code == status.HTTP_200_OK
        assert capability.json()["capabilities"]["test_runs"] is True

        folder = api_key_client.post(
            f"{base}/folders/",
            {"name": "Checkout", "sort_order": 10},
            format="json",
        )
        assert folder.status_code == status.HTTP_201_CREATED
        folder_id = folder.json()["id"]
        renamed = api_key_client.patch(
            f"{base}/folders/{folder_id}/",
            {"name": "Payments"},
            format="json",
        )
        assert renamed.status_code == status.HTTP_200_OK
        assert renamed.json()["name"] == "Payments"

        created = api_key_client.post(
            f"{base}/test-cases/",
            {
                "title": "Card checkout succeeds",
                "folder_id": folder_id,
                "steps": [{"action": {"text": "Submit card"}, "expected_result": {"text": "Paid"}}],
            },
            format="json",
        )
        assert created.status_code == status.HTTP_201_CREATED
        case_id = created.json()["id"]
        updated = api_key_client.patch(
            f"{base}/test-cases/{case_id}/",
            {"title": "Visa checkout succeeds"},
            format="json",
        )
        assert updated.status_code == status.HTTP_200_OK
        assert updated.json()["current_version"] == 2
        version_one = api_key_client.get(f"{base}/test-cases/{case_id}/versions/1/")
        assert version_one.json()["title"] == "Card checkout succeeds"

        requirement = Issue.objects.create(
            workspace=workspace,
            project=project,
            name="Customer can pay by card",
            sequence_id=1,
        )
        links_url = f"{base}/test-cases/{case_id}/work-items/"
        linked = api_key_client.post(links_url, {"issue_id": str(requirement.id)}, format="json")
        assert linked.status_code == status.HTTP_201_CREATED
        assert api_key_client.get(links_url).json()[0]["issue_id"] == str(requirement.id)
        searched = api_key_client.get(
            f"{base}/search/",
            {"query": "type:test_case Visa", "scope": "all"},
        )
        assert searched.status_code == status.HTTP_200_OK
        assert searched.json()["results"][0]["id"] == case_id

        run = api_key_client.post(
            f"{base}/test-runs/",
            {"name": "Agent smoke", "test_case_ids": [case_id]},
            format="json",
        )
        assert run.status_code == status.HTTP_201_CREATED
        run_payload = run.json()
        run_case = run_payload["run_cases"][0]
        assert run_case["test_case_version"]["version"] == 2
        result_url = f"{base}/test-runs/{run_payload['id']}/cases/{run_case['id']}/results/"
        failed = api_key_client.post(
            result_url,
            {"status": "failed", "actual_result": {"text": "HTTP 500"}},
            format="json",
        )
        assert failed.status_code == status.HTTP_201_CREATED
        defect = api_key_client.post(f"{result_url}{failed.json()['id']}/defects/", {}, format="json")
        assert defect.status_code == status.HTTP_201_CREATED
        passed = api_key_client.post(result_url, {"status": "passed"}, format="json")
        assert passed.status_code == status.HTTP_201_CREATED
        closed = api_key_client.post(f"{base}/test-runs/{run_payload['id']}/close/", {}, format="json")
        assert closed.status_code == status.HTTP_200_OK
        assert closed.json()["status"] == "completed"
        assert TestResult.objects.filter(run_case_id=run_case["id"]).count() == 2

        overview = api_key_client.get(f"{base}/overview/")
        coverage = api_key_client.get(f"{base}/requirement-coverage/")
        assert overview.status_code == status.HTTP_200_OK
        assert coverage.status_code == status.HTTP_200_OK
        assert coverage.json()["covered"] == 1

        unlinked = api_key_client.delete(f"{links_url}{requirement.id}/")
        assert unlinked.status_code == status.HTTP_204_NO_CONTENT
        assert api_key_client.get(links_url).json() == []

        archived = api_key_client.delete(f"{base}/test-cases/{case_id}/")
        assert archived.status_code == status.HTTP_204_NO_CONTENT
        assert TestCase.objects.filter(id=case_id, archived_at__isnull=False).exists()
        deleted_folder = api_key_client.delete(f"{base}/folders/{folder_id}/")
        assert deleted_folder.status_code == status.HTTP_204_NO_CONTENT

    def test_non_member_api_key_is_rejected(self, workspace, project):
        outsider = User.objects.create(email="agent-outsider@plane.so", username="agent-outsider")
        token = APIToken.objects.create(user=outsider, label="Outsider", token="outsider-testing-token")
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=token.token)

        response = client.get(f"{_base(workspace, project)}/test-cases/")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_invalid_api_key_is_rejected(self, workspace, project):
        client = APIClient()
        client.credentials(HTTP_X_API_KEY="invalid-testing-token")

        response = client.get(f"{_base(workspace, project)}/test-cases/")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["error"]["code"] == "http_403"
        assert response.json()["error"]["request_id"] == response["X-Request-ID"]

    def test_cross_project_folder_is_rejected_without_partial_case(self, api_key_client, workspace, project):
        other_project = Project.objects.create(
            name="Other project",
            identifier="OTHER",
            workspace=workspace,
            created_by=project.created_by,
        )
        other_folder = TestFolder.objects.create(
            name="Foreign folder",
            project=other_project,
            workspace=workspace,
        )

        response = api_key_client.post(
            f"{_base(workspace, project)}/test-cases/",
            {"title": "Must not be created", "folder_id": str(other_folder.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["error"]["code"] == "http_400"
        assert not TestCase.objects.filter(project=project, versions__title="Must not be created").exists()

    def test_folder_delete_rejects_non_empty_folder(self, api_key_client, workspace, project):
        base = _base(workspace, project)
        folder = api_key_client.post(f"{base}/folders/", {"name": "Not empty"}, format="json").json()
        api_key_client.post(
            f"{base}/test-cases/",
            {"title": "Still active", "folder_id": folder["id"]},
            format="json",
        )

        response = api_key_client.delete(f"{base}/folders/{folder['id']}/")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["error"]["message"] == "Only an empty test folder can be deleted."
        assert response.json()["error"]["code"] == "http_409"
        assert response.json()["error"]["request_id"] == response["X-Request-ID"]

    def test_folder_move_rejects_descendant_cycle(self, api_key_client, workspace, project):
        base = _base(workspace, project)
        parent = api_key_client.post(f"{base}/folders/", {"name": "Parent"}, format="json").json()
        child = api_key_client.post(
            f"{base}/folders/",
            {"name": "Child", "parent_id": parent["id"]},
            format="json",
        ).json()

        response = api_key_client.patch(
            f"{base}/folders/{parent['id']}/",
            {"parent_id": child["id"]},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["error"]["code"] == "http_400"
        assert response.json()["error"]["request_id"] == response["X-Request-ID"]
