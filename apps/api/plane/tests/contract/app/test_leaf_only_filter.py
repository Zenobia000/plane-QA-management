# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""`leaf_only`, on both API surfaces, against the definition `sub_issues_count` uses.

The neighbouring `sub_issue` toggle selects the opposite set -- `sub_issue=false` keeps the
roots and drops every descendant -- so these tests pin the distinction as much as the
feature. The other thing they pin is that "has a child" means a *live* child: archived,
draft and soft-deleted children do not make a parent into a summary, because
`sub_issues_count` counts through `Issue.issue_objects` and the row's number has to agree
with whether the row is shown.
"""

import pytest
from rest_framework import status

from plane.db.models import Issue, Project, ProjectMember, State


@pytest.fixture
def breakdown(db, workspace, create_user):
    """Epic -> Feature -> two Stories, plus a parentless defect-shaped item.

    Leaves: the two stories and the standalone item. Summaries: the epic and the feature.
    """
    project = Project.objects.create(
        name="Leaf Project", identifier="LEAF", workspace=workspace, created_by=create_user
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

    def make(name, parent=None):
        return Issue.objects.create(
            name=name, project=project, workspace=workspace, state=state, parent=parent, created_by=create_user
        )

    epic = make("Traceability capability")
    feature = make("Work-order lookup", parent=epic)
    story_a = make("Look up by work order", parent=feature)
    story_b = make("Look up by serial", parent=feature)
    standalone = make("Write-back returns 503")

    return {
        "project": project,
        "epic": epic,
        "feature": feature,
        "leaves": {story_a, story_b, standalone},
        "summaries": {epic, feature},
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
class TestLeafOnlyOnTheAppAPI:
    def test_off_by_default_the_list_is_the_flat_projection(self, session_client, workspace, breakdown):
        """Upstream behaviour is unchanged when the parameter is absent."""
        response = session_client.get(app_list_url(workspace.slug, breakdown["project"].id))

        assert response.status_code == status.HTTP_200_OK
        returned = names(response.json())
        assert returned == {i.name for i in breakdown["leaves"] | breakdown["summaries"]}

    def test_on_it_drops_the_nodes_that_summarise_others(self, session_client, workspace, breakdown):
        response = session_client.get(app_list_url(workspace.slug, breakdown["project"].id), {"leaf_only": "true"})

        assert response.status_code == status.HTTP_200_OK
        assert names(response.json()) == {i.name for i in breakdown["leaves"]}

    def test_it_is_not_the_same_selection_as_sub_issue_false(self, session_client, workspace, breakdown):
        """`sub_issue=false` keeps roots; `leaf_only` drops them. Opposite ends of the tree."""
        roots = session_client.get(app_list_url(workspace.slug, breakdown["project"].id), {"sub_issue": "false"})
        leaves = session_client.get(app_list_url(workspace.slug, breakdown["project"].id), {"leaf_only": "true"})

        assert names(roots.json()) == {"Traceability capability", "Write-back returns 503"}
        assert names(leaves.json()) == {
            "Look up by work order",
            "Look up by serial",
            "Write-back returns 503",
        }

    def test_a_parent_whose_children_are_all_archived_is_a_leaf_again(self, session_client, workspace, breakdown):
        """`sub_issues_count` counts live children only, and this has to match it."""
        Issue.objects.filter(parent=breakdown["feature"]).update(archived_at="2026-01-01")

        response = session_client.get(app_list_url(workspace.slug, breakdown["project"].id), {"leaf_only": "true"})

        returned = names(response.json())
        assert "Work-order lookup" in returned
        assert "Traceability capability" not in returned


@pytest.mark.contract
@pytest.mark.django_db
class TestLeafOnlyOnTheTokenAPI:
    """Criterion 3: what the UI can ask for, MCP and the CLI have to reach as well."""

    def test_the_token_api_honours_the_same_parameter(self, api_key_client, workspace, breakdown):
        response = api_key_client.get(v1_list_url(workspace.slug, breakdown["project"].id), {"leaf_only": "true"})

        assert response.status_code == status.HTTP_200_OK
        assert names(response.json()) == {i.name for i in breakdown["leaves"]}

    def test_the_token_api_default_is_unchanged(self, api_key_client, workspace, breakdown):
        response = api_key_client.get(v1_list_url(workspace.slug, breakdown["project"].id))

        assert response.status_code == status.HTTP_200_OK
        assert names(response.json()) == {i.name for i in breakdown["leaves"] | breakdown["summaries"]}
