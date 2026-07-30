# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Initiatives, teamspaces and de-dupe.

Initiatives and `Team` were already in the schema and reachable from nowhere the web client
could use. The cases worth pinning are the ones where the obvious behaviour is wrong:
membership is a set rather than an append, and an initiative's percentage has to agree with
the project overview's for the same work.
"""

import pytest
from rest_framework import status

from plane.db.models import (
    Initiative,
    InitiativeProject,
    Issue,
    Project,
    ProjectMember,
    State,
    Team,
    TeamProject,
)


@pytest.fixture
def portfolio(db, workspace, create_user):
    projects = []
    for name, identifier in (("Alpha", "ALPH"), ("Beta", "BETA")):
        project = Project.objects.create(
            name=name, identifier=identifier, workspace=workspace, created_by=create_user
        )
        ProjectMember.objects.create(
            workspace=workspace, project=project, member=create_user, role=20, is_active=True
        )
        projects.append(project)
    return projects


def initiatives_url(workspace):
    return f"/api/workspaces/{workspace.slug}/initiatives/"


def teamspaces_url(workspace):
    return f"/api/workspaces/{workspace.slug}/teamspaces/"


@pytest.mark.contract
@pytest.mark.django_db
class TestInitiatives:
    def test_an_initiative_is_created_and_covers_projects(self, session_client, workspace, portfolio):
        created = session_client.post(
            initiatives_url(workspace), data={"name": "H2 platform"}, content_type="application/json"
        )
        assert created.status_code == status.HTTP_201_CREATED
        initiative_id = created.json()["id"]

        response = session_client.post(
            f"{initiatives_url(workspace)}{initiative_id}/projects/",
            data={"project_ids": [str(p.id) for p in portfolio]},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["project_ids"]) == 2

    def test_membership_is_a_set_rather_than_an_append(self, session_client, workspace, portfolio):
        """Appending would make removing a project impossible through the call that adds one."""
        initiative = Initiative.objects.create(workspace=workspace, name="Narrowing")
        url = f"{initiatives_url(workspace)}{initiative.id}/projects/"
        session_client.post(
            url, data={"project_ids": [str(p.id) for p in portfolio]}, content_type="application/json"
        )

        session_client.post(url, data={"project_ids": [str(portfolio[0].id)]}, content_type="application/json")

        assert InitiativeProject.objects.filter(initiative=initiative).count() == 1

    def test_progress_uses_the_same_denominator_as_the_project_overview(
        self, session_client, workspace, portfolio
    ):
        """Two levels reporting different percentages of the same work is the failure here."""
        initiative = Initiative.objects.create(workspace=workspace, name="Rollup")
        for project in portfolio:
            InitiativeProject.objects.create(initiative=initiative, project=project, workspace=workspace)

        done = State.objects.create(
            workspace=workspace, project=portfolio[0], name="Done", group="completed", sequence=1000
        )
        todo = State.objects.create(
            workspace=workspace, project=portfolio[0], name="Todo", group="unstarted", sequence=2000
        )
        dropped = State.objects.create(
            workspace=workspace, project=portfolio[0], name="Dropped", group="cancelled", sequence=3000
        )
        for state in (done, todo, dropped):
            Issue.objects.create(workspace=workspace, project=portfolio[0], name=state.name, state=state)

        body = session_client.get(f"{initiatives_url(workspace)}{initiative.id}/progress/").json()

        assert body["project_count"] == 2
        assert body["total"] == 3
        # Cancelled work leaves the denominator, exactly as the project overview does it.
        assert body["in_scope"] == 2
        assert body["completion_percentage"] == 50

    def test_a_project_outside_the_workspace_is_dropped_not_refused(
        self, session_client, workspace, portfolio, create_user
    ):
        initiative = Initiative.objects.create(workspace=workspace, name="Partial")

        response = session_client.post(
            f"{initiatives_url(workspace)}{initiative.id}/projects/",
            data={"project_ids": [str(portfolio[0].id), "00000000-0000-0000-0000-000000000000"]},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["project_ids"]) == 1
        assert len(response.json()["dropped"]) == 1


@pytest.mark.contract
@pytest.mark.django_db
class TestTeamspaces:
    def test_a_teamspace_covers_projects_across_the_workspace(self, session_client, workspace, portfolio):
        created = session_client.post(
            teamspaces_url(workspace), data={"name": "Platform"}, content_type="application/json"
        )
        assert created.status_code == status.HTTP_201_CREATED
        team_id = created.json()["id"]

        response = session_client.post(
            f"{teamspaces_url(workspace)}{team_id}/membership/",
            data={"project_ids": [str(p.id) for p in portfolio]},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["project_ids"]) == 2

    def test_membership_is_replaced_as_a_set(self, session_client, workspace, portfolio):
        team = Team.objects.create(workspace=workspace, name="Shrinking")
        url = f"{teamspaces_url(workspace)}{team.id}/membership/"
        session_client.post(
            url, data={"project_ids": [str(p.id) for p in portfolio]}, content_type="application/json"
        )

        session_client.post(url, data={"project_ids": [str(portfolio[1].id)]}, content_type="application/json")

        assert TeamProject.objects.filter(team=team).count() == 1

    def test_omitting_a_key_leaves_that_side_alone(self, session_client, workspace, portfolio):
        """Sending only projects must not clear the members, and the reverse."""
        team = Team.objects.create(workspace=workspace, name="Untouched")
        url = f"{teamspaces_url(workspace)}{team.id}/membership/"
        session_client.post(
            url, data={"project_ids": [str(portfolio[0].id)]}, content_type="application/json"
        )

        session_client.post(url, data={"member_ids": []}, content_type="application/json")

        assert TeamProject.objects.filter(team=team).count() == 1


@pytest.mark.contract
@pytest.mark.django_db
class TestDeDupe:
    def _url(self, workspace, project):
        return f"/api/workspaces/{workspace.slug}/projects/{project.id}/de-dupe/"

    def test_a_similar_title_is_surfaced(self, session_client, workspace, portfolio):
        project = portfolio[0]
        Issue.objects.create(workspace=workspace, project=project, name="Search returns a 500 error")

        response = session_client.get(
            self._url(workspace, project), {"name": "Search returns 500 error"}
        )

        assert response.status_code == status.HTTP_200_OK
        assert [row["name"] for row in response.json()["results"]] == ["Search returns a 500 error"]

    def test_an_unrelated_title_matches_nothing(self, session_client, workspace, portfolio):
        project = portfolio[0]
        Issue.objects.create(workspace=workspace, project=project, name="Search returns a 500 error")

        response = session_client.get(self._url(workspace, project), {"name": "Add dark mode to settings"})

        assert response.json()["results"] == []

    def test_a_short_query_is_not_worth_answering(self, session_client, workspace, portfolio):
        """"fix" and "add" predict nothing, and warning on them trains people to ignore it."""
        project = portfolio[0]
        Issue.objects.create(workspace=workspace, project=project, name="Fix the thing")

        response = session_client.get(self._url(workspace, project), {"name": "fix"})

        assert response.json()["results"] == []

    def test_the_item_being_edited_excludes_itself(self, session_client, workspace, portfolio):
        project = portfolio[0]
        item = Issue.objects.create(workspace=workspace, project=project, name="Search returns a 500 error")

        response = session_client.get(
            self._url(workspace, project), {"name": "Search returns a 500 error", "exclude": str(item.id)}
        )

        assert response.json()["results"] == []
