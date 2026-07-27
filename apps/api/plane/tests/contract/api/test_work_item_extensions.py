# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from rest_framework import status

from plane.db.models import (
    Initiative,
    Issue,
    Milestone,
    Project,
    ProjectIssueType,
    ProjectMember,
    WorkItemProperty,
    WorkItemPropertyValue,
)


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(
        name="Work item extensions",
        identifier="WIE",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20, is_active=True)
    return project


def project_url(workspace, project, suffix):
    return f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}{suffix}"


@pytest.mark.contract
@pytest.mark.django_db
class TestWorkItemExtensionsAPI:
    def test_creates_enables_and_scopes_work_item_types(self, api_key_client, workspace, project, create_user):
        created = api_key_client.post(
            f"/api/v1/workspaces/{workspace.slug}/work-item-types/",
            {"name": "Test case", "description": "A testable requirement"},
            format="json",
        )
        assert created.status_code == status.HTTP_201_CREATED
        type_id = created.json()["id"]

        enabled = api_key_client.post(
            project_url(workspace, project, "/work-item-types/"),
            {"type_id": type_id, "is_default": True},
            format="json",
        )
        assert enabled.status_code == status.HTTP_201_CREATED
        assert enabled.json()["type"]["id"] == type_id
        assert ProjectIssueType.objects.filter(project=project, issue_type_id=type_id, is_default=True).exists()

        other_project = Project.objects.create(
            name="Other project", identifier="OTH", workspace=workspace, created_by=create_user
        )
        ProjectMember.objects.create(
            workspace=workspace, project=other_project, member=create_user, role=20, is_active=True
        )
        rejected = api_key_client.post(
            project_url(workspace, other_project, "/work-items/"),
            {"name": "Type must be enabled per project", "type_id": type_id},
            format="json",
        )
        assert rejected.status_code == status.HTTP_400_BAD_REQUEST
        assert "not enabled" in str(rejected.json())

    def test_creates_typed_property_and_rejects_cross_project_value(
        self, api_key_client, workspace, project, create_user
    ):
        created = api_key_client.post(
            project_url(workspace, project, "/work-item-properties/"),
            {
                "name": "Browser",
                "kind": "select",
                "options": [
                    {"label": "Chrome", "value": "chrome", "sort_order": 10},
                    {"label": "Firefox", "value": "firefox", "sort_order": 20},
                ],
            },
            format="json",
        )
        assert created.status_code == status.HTTP_201_CREATED
        assert created.json()["options"][0]["value"] == "chrome"
        property_id = created.json()["id"]

        issue = Issue.objects.create(workspace=workspace, project=project, name="Browser coverage")
        saved = api_key_client.put(
            project_url(workspace, project, f"/work-items/{issue.id}/properties/{property_id}/"),
            {"value": "chrome"},
            format="json",
        )
        assert saved.status_code == status.HTTP_200_OK
        assert WorkItemPropertyValue.objects.filter(issue=issue, property_id=property_id, value="chrome").exists()

        required_property = api_key_client.post(
            project_url(workspace, project, "/work-item-properties/"),
            {"name": "Build", "kind": "text", "is_required": True},
            format="json",
        ).json()
        missing_required = api_key_client.post(
            project_url(workspace, project, "/work-items/"),
            {"name": "Must provide build"},
            format="json",
        )
        assert missing_required.status_code == status.HTTP_400_BAD_REQUEST
        created_work_item = api_key_client.post(
            project_url(workspace, project, "/work-items/"),
            {"name": "Build is supplied", "properties": {required_property["id"]: "2026.7.27"}},
            format="json",
        )
        assert created_work_item.status_code == status.HTTP_201_CREATED
        assert created_work_item.json()["custom_properties"][required_property["id"]] == "2026.7.27"

        other_project = Project.objects.create(
            name="Foreign property project", identifier="FPP", workspace=workspace, created_by=create_user
        )
        ProjectMember.objects.create(
            workspace=workspace, project=other_project, member=create_user, role=20, is_active=True
        )
        foreign_property = WorkItemProperty.objects.create(
            workspace=workspace, project=other_project, name="Secret", kind="text"
        )
        rejected = api_key_client.put(
            project_url(workspace, project, f"/work-items/{issue.id}/properties/{foreign_property.id}/"),
            {"value": "must not write"},
            format="json",
        )
        assert rejected.status_code == status.HTTP_404_NOT_FOUND
        assert not WorkItemPropertyValue.objects.filter(issue=issue, property=foreign_property).exists()

    def test_creates_milestone_and_workspace_initiative(self, api_key_client, workspace, project):
        milestone = api_key_client.post(
            project_url(workspace, project, "/milestones/"),
            {"name": "MVP", "target_date": "2026-09-01"},
            format="json",
        )
        assert milestone.status_code == status.HTTP_201_CREATED
        assert Milestone.objects.filter(project=project, name="MVP").exists()

        initiative = api_key_client.post(
            f"/api/v1/workspaces/{workspace.slug}/initiatives/",
            {"name": "Quality foundation", "project_ids": [str(project.id)]},
            format="json",
        )
        assert initiative.status_code == status.HTTP_201_CREATED
        assert initiative.json()["projects"] == [
            {"id": str(project.id), "name": project.name, "identifier": project.identifier}
        ]
        assert Initiative.objects.filter(workspace=workspace, name="Quality foundation").exists()
