# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from rest_framework import status

from plane.bgtasks.issue_activities_task import track_type
from plane.db.models import Issue, IssueType, Project, ProjectMember, WorkItemPropertyValue


@pytest.fixture
def extension_project(db, workspace, create_user):
    project = Project.objects.create(
        name="Web work item extensions",
        identifier="WWIE",
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


def project_url(workspace, project, suffix):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}{suffix}"


@pytest.mark.contract
@pytest.mark.django_db
class TestWebWorkItemExtensions:
    def test_type_change_activity_uses_human_readable_names(self, workspace, extension_project):
        old_type = IssueType.objects.create(workspace=workspace, name="Story")
        new_type = IssueType.objects.create(workspace=workspace, name="Defect")
        issue = Issue.objects.create(workspace=workspace, project=extension_project, name="Checkout error")
        activities = []

        track_type(
            requested_data={"type_id": str(new_type.id)},
            current_instance={"type_id": str(old_type.id)},
            issue_id=str(issue.id),
            project_id=str(extension_project.id),
            workspace_id=str(workspace.id),
            actor_id=str(extension_project.created_by_id),
            issue_activities=activities,
            epoch=1,
        )

        assert [(activity.old_value, activity.new_value, activity.field) for activity in activities] == [
            ("Story", "Defect", "type")
        ]

    def test_session_user_can_configure_and_assign_work_item_type(self, session_client, workspace, extension_project):
        created = session_client.post(
            f"/api/workspaces/{workspace.slug}/work-item-types/",
            {"name": "Story", "description": "A measurable requirement", "level": 2},
            format="json",
        )
        assert created.status_code == status.HTTP_201_CREATED

        enabled = session_client.post(
            project_url(workspace, extension_project, "/work-item-types/"),
            {"type_id": created.json()["id"], "level": 2, "is_default": True},
            format="json",
        )
        assert enabled.status_code == status.HTTP_201_CREATED

        work_item = session_client.post(
            project_url(workspace, extension_project, "/issues/"),
            {"name": "Checkout confirmation", "type_id": created.json()["id"]},
            format="json",
        )
        assert work_item.status_code == status.HTTP_201_CREATED, work_item.json()
        assert work_item.json()["type_id"] == created.json()["id"]

        retrieved = session_client.get(project_url(workspace, extension_project, f"/issues/{work_item.json()['id']}/"))
        assert retrieved.status_code == status.HTTP_200_OK
        assert retrieved.json()["type_id"] == created.json()["id"]

        listed = session_client.get(project_url(workspace, extension_project, "/issues/"))
        assert listed.status_code == status.HTTP_200_OK
        assert listed.json()["results"][0]["type_id"] == created.json()["id"]

    def test_session_user_can_define_and_edit_property_value(self, session_client, workspace, extension_project):
        created = session_client.post(
            project_url(workspace, extension_project, "/work-item-properties/"),
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
        issue = Issue.objects.create(
            workspace=workspace,
            project=extension_project,
            name="Cross-browser checkout",
        )

        value_url = project_url(
            workspace,
            extension_project,
            f"/work-items/{issue.id}/properties/{created.json()['id']}/",
        )
        saved = session_client.put(value_url, {"value": "chrome"}, format="json")
        assert saved.status_code == status.HTTP_200_OK
        assert WorkItemPropertyValue.objects.get(issue=issue, property_id=created.json()["id"]).value == "chrome"

        listed = session_client.get(project_url(workspace, extension_project, f"/work-items/{issue.id}/properties/"))
        assert listed.status_code == status.HTTP_200_OK
        assert listed.json()["results"][0]["value"] == "chrome"
