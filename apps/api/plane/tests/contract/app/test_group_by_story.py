# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Grouping the work-item list by story, end to end.

The feature shipped with its store, its layouts, its column builder and an endpoint that
lists the stories to build headings from -- and the list request itself returned 400, because
`parent_id` was never added to `ISSUE_GROUP_BY_ALLOWLIST`. That allowlist exists to keep
user-supplied field names out of the ORM (GHSA-wwgj-929g-42cm), so it fails closed, and a
field nobody added is a field nobody can group by.

Nothing surfaced it. The rejected request left the layout waiting for data that was never
coming, which reads as a hang rather than an error, and the server logged a 400 among a
hundred 200s. So the test that matters is the plain one: the option the UI offers must be an
option the endpoint accepts.
"""

import pytest
from rest_framework import status

from plane.db.models import Issue, IssueType, Project, ProjectIssueType, ProjectMember, State


@pytest.fixture
def project(db, workspace, create_user):
    made = Project.objects.create(name="Grouped", identifier="GRP", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(workspace=workspace, project=made, member=create_user, role=20, is_active=True)
    State.objects.create(workspace=workspace, project=made, name="Todo", group="unstarted", sequence=1000)
    return made


@pytest.fixture
def story_with_a_task(db, workspace, project, create_user):
    story_type = IssueType.objects.create(workspace=workspace, name="Story", level=2)
    task_type = IssueType.objects.create(workspace=workspace, name="Task", level=3)
    for kind, level in ((story_type, 2), (task_type, 3)):
        ProjectIssueType.objects.create(workspace=workspace, project=project, issue_type=kind, level=level)
    story = Issue.objects.create(workspace=workspace, project=project, name="Export orders", type=story_type)
    task = Issue.objects.create(
        workspace=workspace, project=project, name="Write the worker", type=task_type, parent=story
    )
    return story, task


def issues_url(workspace, project, **params):
    query = "&".join(f"{key}={value}" for key, value in params.items())
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/?{query}"


@pytest.mark.contract
@pytest.mark.django_db
class TestGroupByStory:
    def test_the_list_accepts_the_grouping_the_ui_offers(
        self, session_client, workspace, project, story_with_a_task
    ):
        """The exact request the list layout sends. It used to be a 400."""
        response = session_client.get(
            issues_url(
                workspace,
                project,
                group_by="parent_id",
                order_by="-created_at",
                sub_issue="true",
                leaf_only="true",
                layout="list",
                per_page=50,
            )
        )

        assert response.status_code == status.HTTP_200_OK

    def test_a_task_is_grouped_under_its_story(self, session_client, workspace, project, story_with_a_task):
        story, task = story_with_a_task

        body = session_client.get(
            issues_url(workspace, project, group_by="parent_id", sub_issue="true", layout="list", per_page=50)
        ).json()

        # The grouped paginator keys its results by group id, one entry per story plus
        # "None" for work items that hang off nothing at story level.
        grouped = body["results"]
        assert str(story.id) in grouped
        assert [item["name"] for item in grouped[str(story.id)]["results"]] == [task.name]

    def test_grouping_by_an_unlisted_field_is_still_refused(self, session_client, workspace, project):
        """Widening the allowlist by one field must not widen it by any other."""
        response = session_client.get(
            issues_url(workspace, project, group_by="created_by__password", layout="list", per_page=50)
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
