# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""What `IssueType.level` refuses, on every path that can write `parent`.

The rule is stated in `plane.utils.work_item_hierarchy`: a parent may not be narrower than
its child. These tests pin the two halves people get wrong in opposite directions -- that
equal levels are *allowed* (the seeded demo parents a Bug to the Story it was found in),
and that the bulk sub-issue endpoint is not a way around the check.
"""

import pytest
from rest_framework import status

from plane.db.models import Issue, IssueType, Project, ProjectIssueType, ProjectMember


@pytest.fixture
def typed_project(db, workspace, create_user):
    """Epic 0, Feature 1, Story 2, Bug 2 -- the fork's ladder, lower being broader."""
    project = Project.objects.create(
        name="Ladder", identifier="LADR", workspace=workspace, created_by=create_user, is_issue_type_enabled=True
    )
    ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20, is_active=True)

    types = {}
    for name, level, is_epic in (("Epic", 0, True), ("Feature", 1, False), ("Story", 2, False), ("Bug", 2, False)):
        issue_type = IssueType.objects.create(workspace=workspace, name=name, level=level, is_epic=is_epic)
        ProjectIssueType.objects.create(
            project=project, workspace=workspace, issue_type=issue_type, level=level, is_default=name == "Story"
        )
        types[name] = issue_type
    return {"project": project, "types": types}


@pytest.mark.contract
@pytest.mark.django_db
class TestWorkItemHierarchyRules:
    def _detail_url(self, workspace, project, issue):
        return f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/"

    def _sub_issues_url(self, workspace, project, issue):
        return f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/sub-issues/"

    def _item(self, workspace, project, name, issue_type=None, parent=None):
        return Issue.objects.create(
            workspace=workspace, project=project, name=name, type=issue_type, parent=parent
        )

    def test_a_story_cannot_be_given_an_epic_as_a_child(self, session_client, workspace, typed_project):
        project, types = typed_project["project"], typed_project["types"]
        story = self._item(workspace, project, "Story", types["Story"])
        epic = self._item(workspace, project, "Epic", types["Epic"])

        response = session_client.patch(
            self._detail_url(workspace, project, epic),
            data={"parent_id": str(story.id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        epic.refresh_from_db()
        assert epic.parent_id is None

    def test_a_story_under_an_epic_is_the_ordinary_case(self, session_client, workspace, typed_project):
        project, types = typed_project["project"], typed_project["types"]
        epic = self._item(workspace, project, "Epic", types["Epic"])
        story = self._item(workspace, project, "Story", types["Story"])

        response = session_client.patch(
            self._detail_url(workspace, project, story),
            data={"parent_id": str(epic.id)},
            content_type="application/json",
        )

        # A successful work-item PATCH answers 204, not 200.
        assert response.status_code == status.HTTP_204_NO_CONTENT
        story.refresh_from_db()
        assert story.parent_id == epic.id

    def test_equal_levels_nest_because_a_bug_belongs_to_the_story_it_was_found_in(
        self, session_client, workspace, typed_project
    ):
        """The case that rules out `parent.level < child.level`.

        Bug and Story are both level 2 in the seeded ladder, and the demo data parents one
        to the other. A strictly-descending rule would have rejected data this fork already
        ships, which is the definition of breaking something that worked.
        """
        project, types = typed_project["project"], typed_project["types"]
        story = self._item(workspace, project, "Story", types["Story"])
        bug = self._item(workspace, project, "Bug", types["Bug"])

        response = session_client.patch(
            self._detail_url(workspace, project, bug),
            data={"parent_id": str(story.id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        bug.refresh_from_db()
        assert bug.parent_id == story.id

    def test_untyped_work_items_are_left_alone(self, session_client, workspace, typed_project):
        """A project with types switched off has no level to compare, and predates the rule."""
        project = typed_project["project"]
        parent = self._item(workspace, project, "Parent")
        child = self._item(workspace, project, "Child")

        response = session_client.patch(
            self._detail_url(workspace, project, child),
            data={"parent_id": str(parent.id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        child.refresh_from_db()
        assert child.parent_id == parent.id

    def test_retyping_an_item_that_already_has_a_parent_can_also_invert_it(
        self, session_client, workspace, typed_project
    ):
        """The half a parent-only check misses: the item moves up rather than the parent down."""
        project, types = typed_project["project"], typed_project["types"]
        story = self._item(workspace, project, "Story", types["Story"])
        task = self._item(workspace, project, "Detail", types["Bug"], parent=story)

        response = session_client.patch(
            self._detail_url(workspace, project, task),
            data={"type_id": str(types["Epic"].id)},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        task.refresh_from_db()
        assert task.type_id == types["Bug"].id

    def test_the_bulk_sub_issue_endpoint_refuses_the_whole_batch(
        self, session_client, workspace, typed_project
    ):
        """This path writes `parent` without a serializer, so it needs the check of its own.

        Refused whole rather than per item: a partial reparent gives the caller a success
        response and a tree that is half of what they asked for.
        """
        project, types = typed_project["project"], typed_project["types"]
        story = self._item(workspace, project, "Story", types["Story"])
        legal = self._item(workspace, project, "Bug", types["Bug"])
        illegal = self._item(workspace, project, "Epic", types["Epic"])

        response = session_client.post(
            self._sub_issues_url(workspace, project, story),
            data={"sub_issue_ids": [str(legal.id), str(illegal.id)]},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        legal.refresh_from_db()
        illegal.refresh_from_db()
        assert legal.parent_id is None
        assert illegal.parent_id is None

    def test_the_bulk_sub_issue_endpoint_still_accepts_a_legal_batch(
        self, session_client, workspace, typed_project
    ):
        project, types = typed_project["project"], typed_project["types"]
        epic = self._item(workspace, project, "Epic", types["Epic"])
        feature = self._item(workspace, project, "Feature", types["Feature"])
        story = self._item(workspace, project, "Story", types["Story"])

        response = session_client.post(
            self._sub_issues_url(workspace, project, epic),
            data={"sub_issue_ids": [str(feature.id), str(story.id)]},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        feature.refresh_from_db()
        story.refresh_from_db()
        assert feature.parent_id == epic.id
        assert story.parent_id == epic.id
