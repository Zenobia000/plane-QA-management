# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Filtering the work-item list by type, and by the epic role a type plays.

Two parameters, deliberately not one. `issue_type` names specific types and is the key the
frontend has always sent -- it was accepted into the query string and then dropped, because
`ISSUE_FILTER` had no handler for it, so filtering a list by Epic returned everything.
`epic` asks the other question: which type carries `is_epic`, whatever its id is in this
workspace. The epics list asks the second because it cannot know the answer to the first.

Note `type` is neither of these. It was taken by the backlog/active state-group shortcut
long before work item types existed, and it still means that.
"""

import pytest
from rest_framework import status

from plane.db.models import Issue, IssueType, Project, ProjectIssueType, ProjectMember


def list_url(slug, project_id):
    return f"/api/workspaces/{slug}/projects/{project_id}/issues/"


def names(payload):
    rows = payload["results"] if isinstance(payload, dict) and "results" in payload else payload
    return {row["name"] for row in rows}


@pytest.fixture
def typed_backlog(db, workspace, create_user):
    """One epic, one story, one bug, and one work item with no type at all."""
    project = Project.objects.create(
        name="Typed", identifier="TYPD", workspace=workspace, created_by=create_user, is_issue_type_enabled=True
    )
    ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20, is_active=True)

    types = {}
    for name, level, is_epic in (("Epic", 0, True), ("Story", 2, False), ("Bug", 2, False)):
        issue_type = IssueType.objects.create(workspace=workspace, name=name, level=level, is_epic=is_epic)
        ProjectIssueType.objects.create(
            project=project, workspace=workspace, issue_type=issue_type, level=level, is_default=name == "Story"
        )
        types[name] = issue_type

    def make(name, issue_type=None):
        return Issue.objects.create(workspace=workspace, project=project, name=name, type=issue_type)

    return {
        "project": project,
        "types": types,
        "epic": make("Search everywhere", types["Epic"]),
        "story": make("Look up by serial", types["Story"]),
        "bug": make("Write-back returns 503", types["Bug"]),
        "untyped": make("Legacy item"),
    }


@pytest.mark.contract
@pytest.mark.django_db
class TestWorkItemTypeFilters:
    def test_without_a_type_parameter_the_list_is_unchanged(self, session_client, workspace, typed_backlog):
        response = session_client.get(list_url(workspace.slug, typed_backlog["project"].id))

        assert response.status_code == status.HTTP_200_OK
        assert names(response.json()) == {
            "Search everywhere",
            "Look up by serial",
            "Write-back returns 503",
            "Legacy item",
        }

    def test_issue_type_selects_the_named_types(self, session_client, workspace, typed_backlog):
        """The regression this parameter existed for: it used to be accepted and ignored."""
        response = session_client.get(
            list_url(workspace.slug, typed_backlog["project"].id),
            {"issue_type": str(typed_backlog["types"]["Story"].id)},
        )

        assert response.status_code == status.HTTP_200_OK
        assert names(response.json()) == {"Look up by serial"}

    def test_issue_type_accepts_more_than_one(self, session_client, workspace, typed_backlog):
        response = session_client.get(
            list_url(workspace.slug, typed_backlog["project"].id),
            {"issue_type": f"{typed_backlog['types']['Story'].id},{typed_backlog['types']['Bug'].id}"},
        )

        assert names(response.json()) == {"Look up by serial", "Write-back returns 503"}

    def test_issue_type_none_selects_the_untyped(self, session_client, workspace, typed_backlog):
        """Spelled the way labels and assignees spell it, so one convention covers all three."""
        response = session_client.get(
            list_url(workspace.slug, typed_backlog["project"].id), {"issue_type": "None"}
        )

        assert names(response.json()) == {"Legacy item"}

    def test_epic_true_selects_by_the_flag_rather_than_by_id(self, session_client, workspace, typed_backlog):
        response = session_client.get(list_url(workspace.slug, typed_backlog["project"].id), {"epic": "true"})

        assert response.status_code == status.HTTP_200_OK
        assert names(response.json()) == {"Search everywhere"}

    def test_epic_false_is_not_a_filter(self, session_client, workspace, typed_backlog):
        """Deliberate: "not an epic" has to include untyped items, which needs an OR.

        `issue_filters` returns kwargs for `.filter(**filters)` and a kwargs dict cannot
        carry one, so the parameter is ignored rather than answered wrongly. An `epic=false`
        that silently dropped every untyped work item would be worse than its absence.
        """
        response = session_client.get(list_url(workspace.slug, typed_backlog["project"].id), {"epic": "false"})

        assert names(response.json()) == {
            "Search everywhere",
            "Look up by serial",
            "Write-back returns 503",
            "Legacy item",
        }

    def test_epic_does_not_collide_with_the_state_group_shortcut(
        self, session_client, workspace, typed_backlog
    ):
        """`type` still means backlog/active, which is why the type filter is not called that."""
        response = session_client.get(
            list_url(workspace.slug, typed_backlog["project"].id), {"type": "backlog", "epic": "true"}
        )

        assert response.status_code == status.HTTP_200_OK
        # Nothing here has a state, so the state-group predicate excludes everything --
        # the point being that it was applied at all rather than shadowed by `epic`.
        assert names(response.json()) == set()
