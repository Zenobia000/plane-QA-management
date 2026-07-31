# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Applying the SDLC workflow to a project that has the default states.

The interesting part is not creating fifteen rows -- it is not breaking the five that are
already there. `states` is unique on (name, project), and the two sets overlap in three
different ways: identical names, names differing only in case ("In Progress" vs "In
progress"), and names differing in spelling ("Cancelled" vs "Canceled"). Inserting blindly
would either violate the constraint or leave two states meaning the same thing with work
items split between them.
"""

import pytest
from rest_framework import status

from plane.db.models import Issue, Project, ProjectMember, State, WorkspaceMember
from plane.db.models.state import SDLC_STATES


@pytest.fixture
def project(db, workspace, create_user):
    created = Project.objects.create(
        name="Workflow", identifier="WFLW", workspace=workspace, created_by=create_user
    )
    ProjectMember.objects.create(
        workspace=workspace, project=created, member=create_user, role=20, is_active=True
    )
    # What a project created through the UI or the API actually gets.
    for name, group in (
        ("Backlog", "backlog"),
        ("Todo", "unstarted"),
        ("In Progress", "started"),
        ("Done", "completed"),
        ("Cancelled", "cancelled"),
    ):
        State.objects.create(workspace=workspace, project=created, name=name, group=group, sequence=1000)
    return created


def template_url(workspace, project):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/states/workflow-template/"


def live_names(project):
    return list(State.all_state_objects.filter(project=project).values_list("name", flat=True))


@pytest.mark.contract
@pytest.mark.django_db
class TestWorkflowTemplate:
    def test_the_preview_says_what_would_change_without_changing_it(self, session_client, workspace, project):
        before = live_names(project)

        response = session_client.get(template_url(workspace, project))

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "Planning" in body["missing"]
        assert "Backlog" in body["already_present"]
        assert live_names(project) == before

    def test_applying_adds_only_what_is_missing(self, session_client, workspace, project):
        response = session_client.post(template_url(workspace, project))

        assert response.status_code == status.HTTP_201_CREATED
        names = live_names(project)
        # Every SDLC state is now reachable, by its own name or by the equivalent already there.
        assert "Planning" in names
        assert "PR Reviewing" in names
        assert "Wait to Release" in names

    def test_a_name_differing_only_in_case_is_left_alone(self, session_client, workspace, project):
        """"In Progress" already means the SDLC set's "In progress"; two would be a fork."""
        session_client.post(template_url(workspace, project))

        names = live_names(project)
        assert "In Progress" in names
        assert "In progress" not in names

    def test_no_existing_state_is_removed_or_renamed(self, session_client, workspace, project):
        before = set(live_names(project))

        session_client.post(template_url(workspace, project))

        assert before <= set(live_names(project))

    def test_work_items_keep_the_state_they_were_on(self, session_client, workspace, project, create_user):
        doing = State.objects.get(project=project, name="In Progress")
        item = Issue.objects.create(
            name="In flight", project=project, workspace=workspace, state=doing, created_by=create_user
        )

        session_client.post(template_url(workspace, project))

        item.refresh_from_db()
        assert item.state_id == doing.id

    def test_applying_twice_changes_nothing(self, session_client, workspace, project):
        session_client.post(template_url(workspace, project))
        after_first = sorted(live_names(project))

        second = session_client.post(template_url(workspace, project))

        assert second.status_code == status.HTTP_200_OK
        assert second.json()["missing"] == []
        assert sorted(live_names(project)) == after_first

    def test_every_started_state_the_workflow_defines_is_reachable(self, session_client, workspace, project):
        """Nine of the fifteen are `started`; that spread is the point of the set.

        Compared case-insensitively because that is the rule: the project's own
        "In Progress" stands in for the set's "In progress" rather than being duplicated.
        """
        session_client.post(template_url(workspace, project))

        started = {
            name.casefold()
            for name in State.all_state_objects.filter(project=project, group="started").values_list(
                "name", flat=True
            )
        }
        expected = {state["name"].casefold() for state in SDLC_STATES if state["group"] == "started"}
        assert expected <= started

    def test_a_plain_member_cannot_apply_it(self, session_client, workspace, project, create_user):
        """Both memberships are demoted: `allow_permission` also admits a workspace admin
        who belongs to the project, so demoting only the project role proves nothing."""
        ProjectMember.objects.filter(project=project, member=create_user).update(role=15)
        WorkspaceMember.objects.filter(workspace=workspace, member=create_user).update(role=15)

        response = session_client.post(template_url(workspace, project))

        assert response.status_code == status.HTTP_403_FORBIDDEN
