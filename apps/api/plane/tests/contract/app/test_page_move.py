# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Moving a page between projects, which needed no migration.

`ProjectPage` is the membership row and `Page.moved_to_project` the forwarding note; both
have been in the schema all along. The move swaps the membership rather than copying, so
versions and labels stay attached to the same page.
"""

import pytest
from rest_framework import status

from plane.db.models import Page, Project, ProjectMember, ProjectPage


@pytest.fixture
def two_projects(db, workspace, create_user):
    made = []
    for name, identifier in (("Source", "SRC"), ("Target", "TGT")):
        project = Project.objects.create(
            name=name, identifier=identifier, workspace=workspace, created_by=create_user
        )
        ProjectMember.objects.create(
            workspace=workspace, project=project, member=create_user, role=20, is_active=True
        )
        made.append(project)
    return made


def move_url(workspace, project, page):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/{page.id}/move/"


def make_page(workspace, project, owner, name, parent=None):
    page = Page.objects.create(workspace=workspace, name=name, owned_by=owner, parent=parent)
    ProjectPage.objects.create(workspace=workspace, project=project, page=page)
    return page


@pytest.mark.contract
@pytest.mark.django_db
class TestPageMove:
    def test_a_page_changes_project_without_being_copied(
        self, session_client, workspace, two_projects, create_user
    ):
        source, target = two_projects
        page = make_page(workspace, source, create_user, "Runbook")

        response = session_client.post(
            move_url(workspace, source, page),
            data={"project_id": str(target.id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert Page.objects.filter(name="Runbook").count() == 1
        assert ProjectPage.objects.filter(page=page, project=target).exists()
        assert not ProjectPage.objects.filter(page=page, project=source).exists()
        page.refresh_from_db()
        assert str(page.moved_to_project) == str(target.id)

    def test_descendants_follow_their_parent(self, session_client, workspace, two_projects, create_user):
        """A tree split across two projects would leave `parent` crossing a boundary."""
        source, target = two_projects
        root = make_page(workspace, source, create_user, "Root")
        child = make_page(workspace, source, create_user, "Child", parent=root)
        grandchild = make_page(workspace, source, create_user, "Grandchild", parent=child)

        response = session_client.post(
            move_url(workspace, source, root),
            data={"project_id": str(target.id)},
            content_type="application/json",
        )

        assert response.json()["moved"] == 3
        for page in (root, child, grandchild):
            assert ProjectPage.objects.filter(page=page, project=target).exists()

    def test_moving_to_the_same_project_is_refused(self, session_client, workspace, two_projects, create_user):
        source, _target = two_projects
        page = make_page(workspace, source, create_user, "Stay")

        response = session_client.post(
            move_url(workspace, source, page),
            data={"project_id": str(source.id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_a_project_the_user_is_not_in_is_refused(
        self, session_client, workspace, two_projects, create_user
    ):
        source, _target = two_projects
        outsider_project = Project.objects.create(
            name="Outside", identifier="OUT", workspace=workspace, created_by=create_user
        )
        page = make_page(workspace, source, create_user, "Secret")

        response = session_client.post(
            move_url(workspace, source, page),
            data={"project_id": str(outsider_project.id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert ProjectPage.objects.filter(page=page, project=source).exists()
