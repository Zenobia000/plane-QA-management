# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""A folder is declared, not inferred.

Before this, "folder" was whatever happened to have children: a document changed type
because someone else nested something under it, and clicking the folder icon opened a text
editor anyway. The type is now chosen when the row is created, and these pin the three rules
that make that choice mean something -- only folders take children, folders have no document,
and converting between the two cannot silently hide what a page already says.
"""

import pytest
from rest_framework import status

from plane.db.models import Page, Project, ProjectMember, ProjectPage


@pytest.fixture
def project(db, workspace, create_user):
    made = Project.objects.create(name="Docs", identifier="DOC", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(workspace=workspace, project=made, member=create_user, role=20, is_active=True)
    return made


def make(workspace, project, owner, name, *, is_folder=False, parent=None, body="<p></p>"):
    page = Page.objects.create(
        workspace=workspace, name=name, owned_by=owner, parent=parent,
        is_folder=is_folder, description_html=body,
    )
    ProjectPage.objects.create(workspace=workspace, project=project, page=page)
    return page


def pages_url(workspace, project):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/"


def detail_url(workspace, project, page):
    return f"{pages_url(workspace, project)}{page.id}/"


@pytest.mark.contract
@pytest.mark.django_db
class TestOnlyFoldersHoldPages:
    def test_a_page_can_be_created_inside_a_folder(self, session_client, workspace, project, create_user):
        folder = make(workspace, project, create_user, "Test plans", is_folder=True)

        response = session_client.post(
            pages_url(workspace, project),
            data={"name": "Regression scope", "parent": str(folder.id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["parent"] == str(folder.id)

    def test_a_document_cannot_be_used_as_a_container(self, session_client, workspace, project, create_user):
        """The whole point of the type: filing under a document must not make it one."""
        document = make(workspace, project, create_user, "Release notes")

        response = session_client.post(
            pages_url(workspace, project),
            data={"name": "Nested", "parent": str(document.id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not Page.objects.filter(parent=document).exists()

    def test_re_parenting_onto_a_document_is_refused_too(
        self, session_client, workspace, project, create_user
    ):
        """The back door: create legally, then move under a document."""
        folder = make(workspace, project, create_user, "Folder", is_folder=True)
        document = make(workspace, project, create_user, "Doc")
        page = make(workspace, project, create_user, "Child", parent=folder)

        response = session_client.patch(
            detail_url(workspace, project, page),
            data={"parent": str(document.id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        page.refresh_from_db()
        assert page.parent_id == folder.id

    def test_folders_nest_in_folders(self, session_client, workspace, project, create_user):
        outer = make(workspace, project, create_user, "2026", is_folder=True)

        response = session_client.post(
            pages_url(workspace, project),
            data={"name": "Q3", "is_folder": True, "parent": str(outer.id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["is_folder"] is True


@pytest.mark.contract
@pytest.mark.django_db
class TestAFolderHasNoDocument:
    def test_writing_a_body_to_a_folder_is_refused(self, session_client, workspace, project, create_user):
        """The client never opens an editor on a folder; the endpoint does not rely on that."""
        folder = make(workspace, project, create_user, "Meetings", is_folder=True)

        response = session_client.patch(
            f"{detail_url(workspace, project, folder)}description/",
            data={"description_html": "<p>smuggled</p>"},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.contract
@pytest.mark.django_db
class TestConversion:
    def test_an_empty_page_becomes_a_folder(self, session_client, workspace, project, create_user):
        page = make(workspace, project, create_user, "Soon a folder")

        response = session_client.patch(
            detail_url(workspace, project, page), data={"is_folder": True}, content_type="application/json"
        )

        assert response.status_code == status.HTTP_200_OK
        page.refresh_from_db()
        assert page.is_folder is True

    def test_a_page_with_prose_will_not_silently_become_a_folder(
        self, session_client, workspace, project, create_user
    ):
        """A folder never renders its body, so converting would hide what someone wrote."""
        page = make(workspace, project, create_user, "Has content", body="<p>Findings from the audit.</p>")

        response = session_client.patch(
            detail_url(workspace, project, page), data={"is_folder": True}, content_type="application/json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        page.refresh_from_db()
        assert page.is_folder is False
        assert "audit" in page.description_html

    def test_a_folder_holding_pages_will_not_become_a_page(
        self, session_client, workspace, project, create_user
    ):
        folder = make(workspace, project, create_user, "Full", is_folder=True)
        make(workspace, project, create_user, "Inside", parent=folder)

        response = session_client.patch(
            detail_url(workspace, project, folder), data={"is_folder": False}, content_type="application/json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        folder.refresh_from_db()
        assert folder.is_folder is True

    def test_an_empty_folder_becomes_a_page_again(self, session_client, workspace, project, create_user):
        folder = make(workspace, project, create_user, "Empty", is_folder=True)

        response = session_client.patch(
            detail_url(workspace, project, folder), data={"is_folder": False}, content_type="application/json"
        )

        assert response.status_code == status.HTTP_200_OK
        folder.refresh_from_db()
        assert folder.is_folder is False


@pytest.mark.contract
@pytest.mark.django_db
def test_is_folder_is_reported_to_the_client(session_client, workspace, project, create_user):
    """The list is where the client decides between a chevron and a link."""
    make(workspace, project, create_user, "A folder", is_folder=True)
    make(workspace, project, create_user, "A document")

    body = session_client.get(pages_url(workspace, project)).json()

    assert {p["name"]: p["is_folder"] for p in body} == {"A folder": True, "A document": False}
