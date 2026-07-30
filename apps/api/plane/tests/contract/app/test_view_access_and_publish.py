# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Saved-view access and publishing, neither of which needed a migration.

`IssueView.access` and `DeployBoard`'s `"view"` entity type have both been in the schema
all along -- access was gated by being `read_only` on the serializer, and publishing by
`DeployBoardViewSet` hard-coding `entity_name="project"`.
"""

import pytest
from rest_framework import status

from plane.db.models import DeployBoard, IssueView, Project, ProjectMember


@pytest.fixture
def view_project(db, workspace, create_user):
    project = Project.objects.create(name="Views", identifier="VIEW", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20, is_active=True)
    return project


def views_url(workspace, project):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/views/"


def publish_url(workspace, project, view):
    return f"{views_url(workspace, project)}{view.id}/publish/"


@pytest.mark.contract
@pytest.mark.django_db
class TestProjectViewAccess:
    def test_access_can_be_changed_after_creation(self, session_client, workspace, view_project, create_user):
        created = session_client.post(
            views_url(workspace, view_project),
            data={"name": "My work", "filters": {}},
            content_type="application/json",
        )
        assert created.status_code == status.HTTP_201_CREATED
        view_id = created.json()["id"]

        response = session_client.patch(
            f"{views_url(workspace, view_project)}{view_id}/",
            data={"access": 0},
            content_type="application/json",
        )

        # The column, its choices and its default were always there; only the write was gated.
        assert response.status_code == status.HTTP_200_OK
        assert IssueView.objects.get(pk=view_id).access == 0


@pytest.mark.contract
@pytest.mark.django_db
class TestProjectViewPublish:
    def _view(self, workspace, project, owner, access=0):
        return IssueView.objects.create(
            workspace=workspace, project=project, name="Board", query={}, owned_by=owner, access=access
        )

    def test_publishing_creates_an_anchor_and_makes_the_view_public(
        self, session_client, workspace, view_project, create_user
    ):
        view = self._view(workspace, view_project, create_user, access=0)

        response = session_client.post(
            publish_url(workspace, view_project, view), data={}, content_type="application/json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["anchor"]
        assert DeployBoard.objects.filter(entity_name="view", entity_identifier=view.id).count() == 1
        view.refresh_from_db()
        # A private published view is a contradiction the anchor resolves in favour of
        # public anyway, so publishing settles it rather than leaving the two disagreeing.
        assert view.access == 1

    def test_unpublishing_removes_the_anchor(self, session_client, workspace, view_project, create_user):
        view = self._view(workspace, view_project, create_user, access=1)
        session_client.post(publish_url(workspace, view_project, view), data={}, content_type="application/json")

        response = session_client.delete(publish_url(workspace, view_project, view))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not DeployBoard.objects.filter(entity_name="view", entity_identifier=view.id).exists()

    def test_only_the_owner_can_publish(self, session_client, workspace, view_project, create_user, django_user_model):
        other = django_user_model.objects.create(
            email="someone@example.com", username="someone", display_name="Someone"
        )
        view = self._view(workspace, view_project, other, access=1)

        response = session_client.post(
            publish_url(workspace, view_project, view), data={}, content_type="application/json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not DeployBoard.objects.filter(entity_name="view", entity_identifier=view.id).exists()

    def test_an_unpublished_view_reports_no_anchor(self, session_client, workspace, view_project, create_user):
        view = self._view(workspace, view_project, create_user, access=1)

        response = session_client.get(publish_url(workspace, view_project, view))

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {}
