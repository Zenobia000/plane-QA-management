# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from rest_framework import status

from plane.db.models import IssueView, Project, ProjectMember, User


@pytest.fixture
def view_project(db, workspace, create_user):
    project = Project.objects.create(
        name="View Project", identifier="VIEW", workspace=workspace, created_by=create_user
    )
    ProjectMember.objects.create(
        workspace=workspace, project=project, member=create_user, role=20, is_active=True
    )
    return project


def _project_url(workspace, project):
    return f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/views/"


def _workspace_url(workspace):
    return f"/api/v1/workspaces/{workspace.slug}/views/"


@pytest.mark.contract
@pytest.mark.django_db
class TestSavedViewsAPI:
    def test_query_is_compiled_from_filters_rather_than_supplied(
        self, api_key_client, workspace, view_project
    ):
        created = api_key_client.post(
            _project_url(workspace, view_project),
            {
                "name": "Blocked and urgent",
                "filters": {"state_group": ["started"], "priority": ["urgent"]},
                # Deliberately wrong: a caller must never be able to set the
                # compiled lookup, or a view could be made to filter on something
                # its stated filters do not describe.
                "query": {"totally": "ignored"},
            },
            format="json",
        )

        assert created.status_code == status.HTTP_201_CREATED
        body = created.json()
        assert body["query"] == {"state__group__in": ["started"], "priority__in": ["urgent"]}
        assert body["filters"] == {"state_group": ["started"], "priority": ["urgent"]}

    def test_updating_filters_recompiles_the_query(self, api_key_client, workspace, view_project):
        view = api_key_client.post(
            _project_url(workspace, view_project),
            {"name": "Recompile", "filters": {"priority": ["urgent"]}},
            format="json",
        ).json()

        updated = api_key_client.patch(
            f"{_project_url(workspace, view_project)}{view['id']}/",
            {"filters": {"state_group": ["backlog"]}},
            format="json",
        )

        assert updated.json()["query"] == {"state__group__in": ["backlog"]}

    def test_a_locked_view_rejects_updates(self, api_key_client, workspace, view_project):
        view = api_key_client.post(
            _project_url(workspace, view_project), {"name": "Locked"}, format="json"
        ).json()
        api_key_client.patch(
            f"{_project_url(workspace, view_project)}{view['id']}/", {"is_locked": True}, format="json"
        )

        rejected = api_key_client.patch(
            f"{_project_url(workspace, view_project)}{view['id']}/", {"name": "Renamed"}, format="json"
        )

        assert rejected.status_code == status.HTTP_409_CONFLICT
        assert IssueView.objects.get(id=view["id"]).name == "Locked"

    def test_omitting_the_project_creates_a_workspace_view(self, api_key_client, workspace, view_project):
        created = api_key_client.post(_workspace_url(workspace), {"name": "Across projects"}, format="json")

        assert created.status_code == status.HTTP_201_CREATED
        assert created.json()["project"] is None
        # A workspace view must not appear in a project's list, or the two scopes
        # would be indistinguishable to a caller.
        project_views = api_key_client.get(_project_url(workspace, view_project)).json()
        assert created.json()["id"] not in [view["id"] for view in project_views]

    def test_private_views_stay_with_their_owner(self, api_key_client, workspace, view_project):
        mine = api_key_client.post(
            _project_url(workspace, view_project), {"name": "Mine", "access": 0}, format="json"
        ).json()
        theirs = api_key_client.post(
            _project_url(workspace, view_project), {"name": "Theirs", "access": 0}, format="json"
        ).json()
        colleague = User.objects.create(email="colleague@plane.so", username="colleague")
        IssueView.objects.filter(id=theirs["id"]).update(owned_by=colleague)

        listed = [view["id"] for view in api_key_client.get(_project_url(workspace, view_project)).json()]

        # A token acts for its owner, so someone else's private view is not theirs
        # to read even though both accounts belong to the same project.
        assert mine["id"] in listed
        assert theirs["id"] not in listed

    def test_errors_carry_a_code_and_request_identifier(self, api_key_client, workspace, view_project):
        missing = api_key_client.get(
            f"{_project_url(workspace, view_project)}00000000-0000-0000-0000-000000000000/"
        )

        assert missing.status_code == status.HTTP_404_NOT_FOUND
        assert missing.json()["error"]["code"] == "http_404"
        assert missing.json()["error"]["request_id"]
        assert missing["X-Request-ID"]
