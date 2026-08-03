# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The project noticeboard: posting, revising, filing and taking down.

An overview that only reads is half a surface. Announcements are first-hand content -- they
are written here, so they have to be editable and removable here, and the record of who said
what has to survive both. These pin the write path.

Topics are Labels rather than a fixed enum. The point is that no topic name appears in the
source: a team invents its own vocabulary from project settings, and this table only records
which of them an update carries.
"""

import pytest
from rest_framework import status

from plane.db.models import EntityUpdate, EntityUpdateLabel, Label, Project, ProjectMember, User


@pytest.fixture
def project(db, workspace, create_user):
    created = Project.objects.create(
        name="Board", identifier="BORD", workspace=workspace, created_by=create_user
    )
    ProjectMember.objects.create(
        workspace=workspace, project=created, member=create_user, role=20, is_active=True
    )
    return created


@pytest.fixture
def topics(db, workspace, project):
    """A team's own vocabulary. Nothing here is known to the code under test."""
    return {
        name: Label.objects.create(workspace=workspace, project=project, name=name)
        for name in ("市場", "商務", "客戶事件")
    }


@pytest.fixture
def other_member(db, workspace, project):
    user = User.objects.create(email="other@x.com", username="other", is_active=True)
    ProjectMember.objects.create(
        workspace=workspace, project=project, member=user, role=15, is_active=True
    )
    return user


def updates_url(workspace, project):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/updates/"


def post_update(client, workspace, project, **extra):
    payload = {
        "entity_name": "project",
        "entity_identifier": str(project.id),
        "status": "on_track",
        "description": "Shipping on Friday.",
    }
    payload.update(extra)
    return client.post(updates_url(workspace, project), data=payload, content_type="application/json")


@pytest.mark.contract
@pytest.mark.django_db
class TestPostingAndRevising:
    def test_an_update_round_trips(self, session_client, workspace, project):
        created = post_update(session_client, workspace, project)
        assert created.status_code == status.HTTP_201_CREATED
        assert created.json()["is_edited"] is False

        listed = session_client.get(updates_url(workspace, project)).json()
        assert [u["description"] for u in listed] == ["Shipping on Friday."]

    def test_rewriting_the_text_marks_it_edited(self, session_client, workspace, project):
        update_id = post_update(session_client, workspace, project).json()["id"]

        revised = session_client.patch(
            f"{updates_url(workspace, project)}{update_id}/",
            data={"description": "Slipping to Monday."},
            content_type="application/json",
        )

        assert revised.status_code == status.HTTP_200_OK
        assert revised.json()["is_edited"] is True

    def test_filing_under_a_topic_is_not_an_edit(self, session_client, workspace, project, topics):
        """Attaching a topic is filing. It must not put "edited" on what someone said."""
        update_id = post_update(session_client, workspace, project).json()["id"]

        session_client.patch(
            f"{updates_url(workspace, project)}{update_id}/",
            data={"label_ids": [str(topics["市場"].id)]},
            content_type="application/json",
        )

        assert EntityUpdate.objects.get(pk=update_id).edited_at is None

    def test_an_update_can_be_taken_down(self, session_client, workspace, project):
        update_id = post_update(session_client, workspace, project).json()["id"]

        removed = session_client.delete(f"{updates_url(workspace, project)}{update_id}/")

        assert removed.status_code == status.HTTP_204_NO_CONTENT
        assert session_client.get(updates_url(workspace, project)).json() == []


@pytest.mark.contract
@pytest.mark.django_db
class TestTopics:
    def test_topics_attach_and_come_back(self, session_client, workspace, project, topics):
        created = post_update(
            session_client, workspace, project,
            label_ids=[str(topics["客戶事件"].id), str(topics["商務"].id)],
        )

        assert created.status_code == status.HTTP_201_CREATED
        listed = session_client.get(updates_url(workspace, project)).json()
        assert set(listed[0]["label_ids"]) == {str(topics["客戶事件"].id), str(topics["商務"].id)}

    def test_setting_topics_replaces_rather_than_appends(self, session_client, workspace, project, topics):
        update_id = post_update(
            session_client, workspace, project, label_ids=[str(topics["市場"].id)]
        ).json()["id"]

        session_client.patch(
            f"{updates_url(workspace, project)}{update_id}/",
            data={"label_ids": [str(topics["商務"].id)]},
            content_type="application/json",
        )

        remaining = EntityUpdateLabel.objects.filter(entity_update_id=update_id)
        assert [str(link.label_id) for link in remaining] == [str(topics["商務"].id)]

    def test_the_board_filters_by_topic(self, session_client, workspace, project, topics):
        post_update(session_client, workspace, project, description="A", label_ids=[str(topics["市場"].id)])
        post_update(session_client, workspace, project, description="B", label_ids=[str(topics["商務"].id)])

        filtered = session_client.get(f"{updates_url(workspace, project)}?label={topics['市場'].id}").json()

        assert [u["description"] for u in filtered] == ["A"]

    def test_a_topic_from_another_project_is_rejected(
        self, session_client, workspace, project, create_user
    ):
        elsewhere = Project.objects.create(
            name="Elsewhere", identifier="ELSE", workspace=workspace, created_by=create_user
        )
        foreign = Label.objects.create(workspace=workspace, project=elsewhere, name="別的")

        response = post_update(session_client, workspace, project, label_ids=[str(foreign.id)])

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.contract
@pytest.mark.django_db
class TestWhoMayChangeIt:
    def test_a_member_cannot_rewrite_someone_elses_post(
        self, session_client, api_client, workspace, project, other_member
    ):
        update_id = post_update(session_client, workspace, project).json()["id"]
        api_client.force_authenticate(user=other_member)

        response = api_client.patch(
            f"{updates_url(workspace, project)}{update_id}/",
            data={"description": "Rewritten by someone else."},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert EntityUpdate.objects.get(pk=update_id).description == "Shipping on Friday."

    def test_a_member_cannot_take_down_someone_elses_post(
        self, session_client, api_client, workspace, project, other_member
    ):
        update_id = post_update(session_client, workspace, project).json()["id"]
        api_client.force_authenticate(user=other_member)

        response = api_client.delete(f"{updates_url(workspace, project)}{update_id}/")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_an_admin_can_moderate(self, session_client, api_client, workspace, project, other_member):
        """A board nobody can moderate is its own problem."""
        ProjectMember.objects.filter(project=project, member=other_member).update(role=20)
        update_id = post_update(session_client, workspace, project).json()["id"]
        api_client.force_authenticate(user=other_member)

        response = api_client.delete(f"{updates_url(workspace, project)}{update_id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT
