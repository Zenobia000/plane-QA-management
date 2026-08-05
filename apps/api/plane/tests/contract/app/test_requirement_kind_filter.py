# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Selecting work items by what they state, on both API surfaces.

The classification was writable before this filter existed, which made it a field you could
fill in and then never query -- "show me every NFR" meant listing the project and filtering
client-side. These tests pin the selection itself and two things about how it fails.

The first is that the nature axis crosses the breakdown axis: an epic and a story can both be
quality requirements, so filtering by kind must not become a filter by level. The fixture puts
a quality requirement at two different depths for that reason.

The second is that a kind nobody defined returns nothing rather than everything. `issue_type`
shipped as a parameter the server dropped on the floor, so filtering by Epic returned the
whole project, and it looked like a working filter over a project with no types.
"""

import pytest
from rest_framework import status

from plane.db.models import Issue, Project, ProjectMember, State


@pytest.fixture
def classified(db, workspace, create_user):
    """Two quality requirements at different depths, two functional, one of neither."""
    project = Project.objects.create(
        name="Kind Project", identifier="KIND", workspace=workspace, created_by=create_user
    )
    ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20, is_active=True)
    state = State.objects.create(
        name="In progress",
        color="#F59E0B",
        group="started",
        sequence=15000,
        project=project,
        workspace=workspace,
        created_by=create_user,
        default=True,
    )

    def make(name, kind, parent=None):
        return Issue.objects.create(
            name=name,
            project=project,
            workspace=workspace,
            state=state,
            parent=parent,
            requirement_kind=kind,
            created_by=create_user,
        )

    # An epic-shaped quality requirement: "the notification service is reliable" is a promise
    # about a whole capability, not a story under one.
    reliability = make("Notification service stays reliable", "quality")
    checkout = make("Checkout", "functional")
    latency = make("Checkout P95 under 2s at peak", "quality", parent=checkout)
    refund = make("Agent can refund a paid, unshipped order", "functional", parent=checkout)
    plumbing = make("Add the retry queue", "none", parent=checkout)

    return {
        "project": project,
        "quality": {reliability, latency},
        "functional": {checkout, refund},
        "none": {plumbing},
    }


def app_list_url(slug, project_id):
    return f"/api/workspaces/{slug}/projects/{project_id}/issues/"


def v1_list_url(slug, project_id):
    return f"/api/v1/workspaces/{slug}/projects/{project_id}/work-items/"


def names(payload):
    rows = payload["results"] if isinstance(payload, dict) and "results" in payload else payload
    return {row["name"] for row in rows}


@pytest.mark.contract
@pytest.mark.django_db
class TestRequirementKindOnTheAppAPI:
    def test_absent_the_parameter_changes_nothing(self, session_client, workspace, classified):
        response = session_client.get(app_list_url(workspace.slug, classified["project"].id))

        assert response.status_code == status.HTTP_200_OK
        every = classified["quality"] | classified["functional"] | classified["none"]
        assert names(response.json()) == {i.name for i in every}

    def test_quality_selects_the_nfrs_at_every_depth(self, session_client, workspace, classified):
        """The epic-level one is the point: nature is not a level."""
        response = session_client.get(
            app_list_url(workspace.slug, classified["project"].id), {"requirement_kind": "quality"}
        )

        assert response.status_code == status.HTTP_200_OK
        assert names(response.json()) == {i.name for i in classified["quality"]}

    def test_several_kinds_at_once_are_a_union(self, session_client, workspace, classified):
        response = session_client.get(
            app_list_url(workspace.slug, classified["project"].id),
            {"requirement_kind": "functional,quality"},
        )

        assert response.status_code == status.HTTP_200_OK
        requirements = classified["quality"] | classified["functional"]
        assert names(response.json()) == {i.name for i in requirements}
        assert "Add the retry queue" not in names(response.json())

    def test_none_is_askable_by_name_rather_than_being_a_null(self, session_client, workspace, classified):
        """Work items that state no requirement carry `none`; the column is never null."""
        response = session_client.get(
            app_list_url(workspace.slug, classified["project"].id), {"requirement_kind": "none"}
        )

        assert response.status_code == status.HTTP_200_OK
        assert names(response.json()) == {i.name for i in classified["none"]}

    def test_a_kind_that_does_not_exist_returns_nothing_not_everything(self, session_client, workspace, classified):
        """The `issue_type` failure: a dropped parameter reads as "there are none of these"."""
        response = session_client.get(
            app_list_url(workspace.slug, classified["project"].id), {"requirement_kind": "NFR"}
        )

        assert response.status_code == status.HTTP_200_OK
        assert names(response.json()) == set()


@pytest.mark.contract
@pytest.mark.django_db
class TestRequirementKindOnTheTokenAPI:
    """Criterion 3: what the UI can ask for, MCP and the CLI have to reach as well."""

    def test_the_token_api_honours_the_same_parameter(self, api_key_client, workspace, classified):
        response = api_key_client.get(
            v1_list_url(workspace.slug, classified["project"].id), {"requirement_kind": "quality"}
        )

        assert response.status_code == status.HTTP_200_OK
        assert names(response.json()) == {i.name for i in classified["quality"]}

    def test_the_token_api_default_is_unchanged(self, api_key_client, workspace, classified):
        response = api_key_client.get(v1_list_url(workspace.slug, classified["project"].id))

        assert response.status_code == status.HTTP_200_OK
        every = classified["quality"] | classified["functional"] | classified["none"]
        assert names(response.json()) == {i.name for i in every}

    def test_an_unrelated_parameter_is_still_ignored_here(self, api_key_client, workspace, classified):
        """Only this one predicate was wired in.

        Routing the whole of `issue_filters` into this endpoint would have switched on every
        other filter at once, including the label and assignee joins that multiply rows, which
        is a behaviour change to every caller of this endpoint and not what this change is for.

        This pins the blast radius, not a desirable contract. `priority` being dropped here is
        a real gap of the same shape as the one above -- the MCP `issue_list` tool advertises
        the parameter, so an agent filtering by it gets the whole project back and has no way
        to tell. Fixing that means deciding which of the filters this endpoint should honour,
        which is a wider question than one field.
        """
        response = api_key_client.get(v1_list_url(workspace.slug, classified["project"].id), {"priority": "urgent"})

        assert response.status_code == status.HTTP_200_OK
        every = classified["quality"] | classified["functional"] | classified["none"]
        assert names(response.json()) == {i.name for i in every}
