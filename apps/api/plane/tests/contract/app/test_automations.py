# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Automation rules, and the two properties that matter more than expressiveness.

A rule cannot trigger another rule, because actions write fields directly rather than going
back through the update path. And a rule whose action names something deleted is skipped
rather than raised, so a tidied project does not start failing every save.
"""

import pytest
from rest_framework import status

from plane.db.models import Automation, Issue, IssueLabel, Label, Project, ProjectMember, State


@pytest.fixture
def automated(db, workspace, create_user):
    project = Project.objects.create(name="Auto", identifier="AUTO", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20, is_active=True)
    states = {
        name: State.objects.create(workspace=workspace, project=project, name=name, group=group, sequence=seq)
        for name, group, seq in (("Todo", "unstarted", 1000), ("Done", "completed", 2000))
    }
    return {"project": project, "states": states}


def issue_url(workspace, project, issue):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/"


@pytest.mark.contract
@pytest.mark.django_db
class TestAutomations:
    def test_a_rule_fires_when_its_state_group_is_entered(self, session_client, workspace, automated):
        project, states = automated["project"], automated["states"]
        Automation.objects.create(
            workspace=workspace,
            project=project,
            name="Drop priority on completion",
            trigger_state_group="completed",
            actions={"priority": "low"},
        )
        item = Issue.objects.create(
            workspace=workspace, project=project, name="Ship", state=states["Todo"], priority="urgent"
        )

        response = session_client.patch(
            issue_url(workspace, project, item),
            data={"state_id": str(states["Done"].id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        item.refresh_from_db()
        assert item.priority == "low"

    def test_a_rule_does_not_fire_when_the_group_is_unchanged(self, session_client, workspace, automated):
        """Editing something else on an item already in the group must not re-run the rule."""
        project, states = automated["project"], automated["states"]
        Automation.objects.create(
            workspace=workspace,
            project=project,
            name="Drop priority",
            trigger_state_group="completed",
            actions={"priority": "low"},
        )
        item = Issue.objects.create(
            workspace=workspace, project=project, name="Already done", state=states["Done"], priority="urgent"
        )

        session_client.patch(
            issue_url(workspace, project, item), data={"name": "Renamed"}, content_type="application/json"
        )

        item.refresh_from_db()
        assert item.priority == "urgent"

    def test_an_inactive_rule_is_ignored(self, session_client, workspace, automated):
        project, states = automated["project"], automated["states"]
        Automation.objects.create(
            workspace=workspace,
            project=project,
            name="Off",
            trigger_state_group="completed",
            is_active=False,
            actions={"priority": "low"},
        )
        item = Issue.objects.create(
            workspace=workspace, project=project, name="Ship", state=states["Todo"], priority="urgent"
        )

        session_client.patch(
            issue_url(workspace, project, item),
            data={"state_id": str(states["Done"].id)},
            content_type="application/json",
        )

        item.refresh_from_db()
        assert item.priority == "urgent"

    def test_rules_that_undo_each_other_cannot_loop(self, session_client, workspace, automated):
        """The structural property: an action can never be the thing that triggers a rule.

        Both rules target the same group, so a design that re-evaluated after each action
        would alternate forever. Writing fields directly means each fires exactly once.
        """
        project, states = automated["project"], automated["states"]
        for name, priority in (("Raise", "urgent"), ("Lower", "low")):
            Automation.objects.create(
                workspace=workspace,
                project=project,
                name=name,
                trigger_state_group="completed",
                actions={"priority": priority},
            )
        item = Issue.objects.create(
            workspace=workspace, project=project, name="Contested", state=states["Todo"], priority="medium"
        )

        response = session_client.patch(
            issue_url(workspace, project, item),
            data={"state_id": str(states["Done"].id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        item.refresh_from_db()
        # Whichever ran last wins; the point is that the request returns at all.
        assert item.priority in ("urgent", "low")

    def test_a_label_action_attaches_the_label(self, session_client, workspace, automated):
        project, states = automated["project"], automated["states"]
        label = Label.objects.create(workspace=workspace, project=project, name="shipped")
        Automation.objects.create(
            workspace=workspace,
            project=project,
            name="Tag shipped",
            trigger_state_group="completed",
            actions={"label_ids": [str(label.id)]},
        )
        item = Issue.objects.create(workspace=workspace, project=project, name="Ship", state=states["Todo"])

        session_client.patch(
            issue_url(workspace, project, item),
            data={"state_id": str(states["Done"].id)},
            content_type="application/json",
        )

        assert IssueLabel.objects.filter(issue=item, label=label).count() == 1
