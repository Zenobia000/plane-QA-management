# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Filing pages under other pages, which needed no migration either.

`Page.parent` has been in the schema all along, and the archive and move cascades were already
built on it -- but the list queryset ended in `.filter(parent__isnull=True)`, so a sub-page was
returned by nothing and reachable from nowhere. These tests pin the hierarchy now that it is
visible, and pin the one thing the old code never had to think about: a page filed inside its
own sub-tree would close the tree into a ring and spin the traversals forever.
"""

import pytest
from rest_framework import status

from plane.db.models import Page, Project, ProjectMember, ProjectPage


@pytest.fixture
def project(db, workspace, create_user):
    made = Project.objects.create(name="Docs", identifier="DOC", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(
        workspace=workspace, project=made, member=create_user, role=20, is_active=True
    )
    return made


def make_page(workspace, project, owner, name, parent=None):
    page = Page.objects.create(workspace=workspace, name=name, owned_by=owner, parent=parent)
    ProjectPage.objects.create(workspace=workspace, project=project, page=page)
    return page


def list_url(workspace, project):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/"


def detail_url(workspace, project, page):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/{page.id}/"


@pytest.mark.contract
@pytest.mark.django_db
class TestPageHierarchy:
    def test_sub_pages_are_listed_alongside_their_parents(self, session_client, workspace, project, create_user):
        root = make_page(workspace, project, create_user, "Test plan")
        child = make_page(workspace, project, create_user, "Sprint 12 regression", parent=root)

        response = session_client.get(list_url(workspace, project))

        assert response.status_code == status.HTTP_200_OK
        listed = {page["id"]: page for page in response.json()}
        assert str(root.id) in listed
        assert str(child.id) in listed
        assert listed[str(child.id)]["parent"] == str(root.id)
        assert listed[str(root.id)]["parent"] is None

    def test_a_sub_page_can_be_opened(self, session_client, workspace, project, create_user):
        root = make_page(workspace, project, create_user, "Test plan")
        child = make_page(workspace, project, create_user, "Smoke checklist", parent=root)

        response = session_client.get(detail_url(workspace, project, child))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["parent"] == str(root.id)

    def test_a_page_can_be_filed_under_another(self, session_client, workspace, project, create_user):
        root = make_page(workspace, project, create_user, "Test plan")
        loose = make_page(workspace, project, create_user, "Defect weekly")

        response = session_client.patch(
            detail_url(workspace, project, loose),
            data={"parent": str(root.id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        loose.refresh_from_db()
        assert loose.parent_id == root.id

    def test_a_sub_page_can_be_returned_to_the_top_level(self, session_client, workspace, project, create_user):
        root = make_page(workspace, project, create_user, "Test plan")
        child = make_page(workspace, project, create_user, "Smoke checklist", parent=root)

        response = session_client.patch(
            detail_url(workspace, project, child),
            data={"parent": None},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        child.refresh_from_db()
        assert child.parent_id is None

    def test_a_page_cannot_be_its_own_parent(self, session_client, workspace, project, create_user):
        page = make_page(workspace, project, create_user, "Test plan")

        response = session_client.patch(
            detail_url(workspace, project, page),
            data={"parent": str(page.id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        page.refresh_from_db()
        assert page.parent_id is None

    def test_a_page_cannot_be_filed_inside_its_own_sub_tree(
        self, session_client, workspace, project, create_user
    ):
        """The ring the archive CTE and the move walk would never come back from."""
        root = make_page(workspace, project, create_user, "Test plan")
        child = make_page(workspace, project, create_user, "Sprint 12", parent=root)
        grandchild = make_page(workspace, project, create_user, "Smoke", parent=child)

        response = session_client.patch(
            detail_url(workspace, project, root),
            data={"parent": str(grandchild.id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        root.refresh_from_db()
        assert root.parent_id is None

    def test_a_parent_from_another_project_is_refused(self, session_client, workspace, project, create_user):
        elsewhere = Project.objects.create(
            name="Other", identifier="OTH", workspace=workspace, created_by=create_user
        )
        ProjectMember.objects.create(
            workspace=workspace, project=elsewhere, member=create_user, role=20, is_active=True
        )
        outsider = make_page(workspace, elsewhere, create_user, "Somewhere else")
        page = make_page(workspace, project, create_user, "Test plan")

        response = session_client.patch(
            detail_url(workspace, project, page),
            data={"parent": str(outsider.id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        page.refresh_from_db()
        assert page.parent_id is None

    def test_a_sub_page_can_be_created_directly_under_its_parent(
        self, session_client, workspace, project, create_user
    ):
        root = make_page(workspace, project, create_user, "Test plan")

        response = session_client.post(
            list_url(workspace, project),
            data={"name": "Sprint 12 regression", "parent": str(root.id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["parent"] == str(root.id)

    def test_creating_under_a_page_from_another_project_is_refused(
        self, session_client, workspace, project, create_user
    ):
        elsewhere = Project.objects.create(
            name="Other", identifier="OTH", workspace=workspace, created_by=create_user
        )
        ProjectMember.objects.create(
            workspace=workspace, project=elsewhere, member=create_user, role=20, is_active=True
        )
        outsider = make_page(workspace, elsewhere, create_user, "Somewhere else")

        response = session_client.post(
            list_url(workspace, project),
            data={"name": "Orphan", "parent": str(outsider.id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not Page.objects.filter(name="Orphan").exists()

    def test_archiving_a_parent_takes_its_sub_tree_with_it(
        self, session_client, workspace, project, create_user
    ):
        root = make_page(workspace, project, create_user, "Test plan")
        child = make_page(workspace, project, create_user, "Sprint 12", parent=root)
        grandchild = make_page(workspace, project, create_user, "Smoke", parent=child)

        response = session_client.post(f"{detail_url(workspace, project, root)}archive/")

        assert response.status_code == status.HTTP_200_OK
        for page in (root, child, grandchild):
            page.refresh_from_db()
            assert page.archived_at is not None
