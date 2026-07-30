# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Workflows, worklogs and templates.

The cases that matter are the ones where a cheaper rule would have been wrong: a project
with no transitions must stay unconstrained, a state nobody has written a rule for must stay
unconstrained even when its neighbours are, and a template must survive the deletion of
something it names.
"""

import pytest
from rest_framework import status

from plane.db.models import Issue, Project, ProjectMember, State, StateTransition, Template, Worklog


@pytest.fixture
def flow_project(db, workspace, create_user):
    project = Project.objects.create(
        name="Flow", identifier="FLOW", workspace=workspace, created_by=create_user, is_time_tracking_enabled=True
    )
    ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20, is_active=True)
    states = {
        name: State.objects.create(
            workspace=workspace, project=project, name=name, group=group, sequence=seq
        )
        for name, group, seq in (
            ("Todo", "unstarted", 1000),
            ("Doing", "started", 2000),
            ("Done", "completed", 3000),
        )
    }
    return {"project": project, "states": states}


def issue_url(workspace, project, issue):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/"


def transitions_url(workspace, project):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/state-transitions/"


def worklogs_url(workspace, project, issue):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/worklogs/"


def worklog_summary_url(workspace, project, issue):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/worklog-summary/"


@pytest.mark.contract
@pytest.mark.django_db
class TestWorkflows:
    def test_a_project_with_no_transitions_allows_every_move(self, session_client, workspace, flow_project):
        """Every existing project is this one. Switching the feature on cannot break them."""
        project, states = flow_project["project"], flow_project["states"]
        item = Issue.objects.create(workspace=workspace, project=project, name="Free", state=states["Todo"])

        response = session_client.patch(
            issue_url(workspace, project, item),
            data={"state_id": str(states["Done"].id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_once_a_state_has_an_edge_only_that_edge_is_legal(self, session_client, workspace, flow_project):
        project, states = flow_project["project"], flow_project["states"]
        StateTransition.objects.create(
            workspace=workspace, project=project, from_state=states["Todo"], to_state=states["Doing"]
        )
        item = Issue.objects.create(workspace=workspace, project=project, name="Guarded", state=states["Todo"])

        allowed = session_client.patch(
            issue_url(workspace, project, item),
            data={"state_id": str(states["Doing"].id)},
            content_type="application/json",
        )
        assert allowed.status_code == status.HTTP_204_NO_CONTENT

        item.state = states["Todo"]
        item.save(update_fields=["state"])
        refused = session_client.patch(
            issue_url(workspace, project, item),
            data={"state_id": str(states["Done"].id)},
            content_type="application/json",
        )
        assert refused.status_code == status.HTTP_400_BAD_REQUEST

    def test_a_state_nobody_constrained_stays_unconstrained(self, session_client, workspace, flow_project):
        """The rule is scoped to the source state, which is what lets a workflow be adopted
        one state at a time rather than all at once."""
        project, states = flow_project["project"], flow_project["states"]
        StateTransition.objects.create(
            workspace=workspace, project=project, from_state=states["Todo"], to_state=states["Doing"]
        )
        item = Issue.objects.create(workspace=workspace, project=project, name="Elsewhere", state=states["Doing"])

        response = session_client.patch(
            issue_url(workspace, project, item),
            data={"state_id": str(states["Todo"].id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_an_approval_edge_with_no_approvers_is_refused_for_everyone(
        self, session_client, workspace, flow_project
    ):
        """A rule nobody can satisfy is more likely half-finished than intended."""
        project, states = flow_project["project"], flow_project["states"]
        StateTransition.objects.create(
            workspace=workspace,
            project=project,
            from_state=states["Doing"],
            to_state=states["Done"],
            requires_approval=True,
        )
        item = Issue.objects.create(workspace=workspace, project=project, name="Needs sign-off", state=states["Doing"])

        response = session_client.patch(
            issue_url(workspace, project, item),
            data={"state_id": str(states["Done"].id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_a_designated_approver_may_make_the_move(self, session_client, workspace, flow_project, create_user):
        project, states = flow_project["project"], flow_project["states"]
        created = session_client.post(
            transitions_url(workspace, project),
            data={
                "from_state": str(states["Doing"].id),
                "to_state": str(states["Done"].id),
                "requires_approval": True,
                "approver_ids": [str(create_user.id)],
            },
            content_type="application/json",
        )
        assert created.status_code == status.HTTP_201_CREATED
        item = Issue.objects.create(workspace=workspace, project=project, name="Approved", state=states["Doing"])

        response = session_client.patch(
            issue_url(workspace, project, item),
            data={"state_id": str(states["Done"].id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_a_transition_between_projects_states_is_refused(
        self, session_client, workspace, flow_project, create_user
    ):
        project, states = flow_project["project"], flow_project["states"]
        other = Project.objects.create(name="Other", identifier="OTH3", workspace=workspace, created_by=create_user)
        ProjectMember.objects.create(workspace=workspace, project=other, member=create_user, role=20, is_active=True)
        foreign = State.objects.create(
            workspace=workspace, project=other, name="Elsewhere", group="started", sequence=1000
        )

        response = session_client.post(
            transitions_url(workspace, project),
            data={"from_state": str(states["Todo"].id), "to_state": str(foreign.id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.contract
@pytest.mark.django_db
class TestWorklogs:
    def test_time_is_logged_and_summed_per_member(self, session_client, workspace, flow_project):
        project = flow_project["project"]
        item = Issue.objects.create(workspace=workspace, project=project, name="Tracked")

        for minutes in (90, 30):
            created = session_client.post(
                worklogs_url(workspace, project, item),
                data={"duration": minutes, "logged_at": "2026-07-30", "description": "work"},
                content_type="application/json",
            )
            assert created.status_code == status.HTTP_201_CREATED

        summary = session_client.get(worklog_summary_url(workspace, project, item)).json()
        assert summary["duration"] == 120
        assert summary["by_member"][0]["duration"] == 120

    def test_a_project_without_time_tracking_refuses_writes(self, session_client, workspace, create_user):
        """The flag shipped years before anything could be logged against it."""
        project = Project.objects.create(
            name="Untracked", identifier="UNTR", workspace=workspace, created_by=create_user
        )
        ProjectMember.objects.create(
            workspace=workspace, project=project, member=create_user, role=20, is_active=True
        )
        item = Issue.objects.create(workspace=workspace, project=project, name="No time")

        response = session_client.post(
            worklogs_url(workspace, project, item),
            data={"duration": 60, "logged_at": "2026-07-30"},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not Worklog.objects.filter(issue=item).exists()

    def test_a_zero_duration_is_refused(self, session_client, workspace, flow_project):
        project = flow_project["project"]
        item = Issue.objects.create(workspace=workspace, project=project, name="Nothing")

        response = session_client.post(
            worklogs_url(workspace, project, item),
            data={"duration": 0, "logged_at": "2026-07-30"},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.contract
@pytest.mark.django_db
class TestTemplates:
    def _apply_url(self, workspace, project, template):
        return f"/api/workspaces/{workspace.slug}/projects/{project.id}/templates/{template.id}/apply/"

    def test_a_work_item_is_created_from_a_saved_shape(self, session_client, workspace, flow_project):
        project, states = flow_project["project"], flow_project["states"]
        template = Template.objects.create(
            workspace=workspace,
            kind=Template.Kind.WORK_ITEM,
            name="Bug report",
            payload={"name": "Bug: ", "priority": "high", "state_id": str(states["Todo"].id)},
        )

        response = session_client.post(
            self._apply_url(workspace, project, template),
            data={"name": "Bug: search returns 500"},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["dropped"] == []
        created = Issue.objects.get(pk=response.json()["id"])
        assert created.name == "Bug: search returns 500"
        assert created.priority == "high"
        assert created.state_id == states["Todo"].id

    def test_a_template_survives_the_deletion_of_something_it_names(
        self, session_client, workspace, flow_project
    ):
        """A template outlives the schema it was written against.

        Raising here would make a template unusable the first time somebody tidies a project,
        with no way to see what it was trying to do.
        """
        project, states = flow_project["project"], flow_project["states"]
        template = Template.objects.create(
            workspace=workspace,
            kind=Template.Kind.WORK_ITEM,
            name="Stale",
            payload={"name": "From stale template", "state_id": str(states["Done"].id)},
        )
        states["Done"].delete()

        response = session_client.post(
            self._apply_url(workspace, project, template), data={}, content_type="application/json"
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["dropped"] == ["state_id"]

    def test_a_template_with_no_name_cannot_create(self, session_client, workspace, flow_project):
        project = flow_project["project"]
        template = Template.objects.create(
            workspace=workspace, kind=Template.Kind.WORK_ITEM, name="Empty", payload={"priority": "low"}
        )

        response = session_client.post(
            self._apply_url(workspace, project, template), data={}, content_type="application/json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
