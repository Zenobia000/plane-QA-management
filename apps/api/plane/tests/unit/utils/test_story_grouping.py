# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Which work items become columns when the list groups by parent.

The rule is `level == 2`, and the reason is bounded output: the paginator opens one window
partition and builds one response entry per value this returns, so "anything with a child"
would put a column on the page for every parent in a growing backlog. These tests pin the
boundary from both sides -- the levels that must not leak in, and the level-2 rows that must
appear even when nothing hangs off them yet.
"""

import pytest

from plane.db.models import Issue, IssueType, Project, ProjectMember
from plane.utils.grouper import issue_group_values, story_grouping_queryset


@pytest.fixture
def project(db, workspace, create_user):
    p = Project.objects.create(name="Grouping", identifier="GRP", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(workspace=workspace, project=p, member=create_user, role=20, is_active=True)
    return p


@pytest.fixture
def types(db, workspace):
    return {
        name: IssueType.objects.create(workspace=workspace, name=name, level=level, is_epic=is_epic)
        for name, level, is_epic in (
            ("Epic", 0, True),
            ("Feature", 1, False),
            ("Story", 2, False),
            ("Bug", 2, False),
            ("Task", 3, False),
        )
    }


def _issue(workspace, project, name, issue_type, parent=None):
    return Issue.objects.create(workspace=workspace, project=project, name=name, type=issue_type, parent=parent)


def test_only_level_two_becomes_a_column(workspace, project, types):
    epic = _issue(workspace, project, "An epic", types["Epic"])
    feature = _issue(workspace, project, "A feature", types["Feature"], parent=epic)
    story = _issue(workspace, project, "A story", types["Story"], parent=feature)
    _issue(workspace, project, "A task", types["Task"], parent=story)

    ids = set(story_grouping_queryset(workspace.slug, project.id).values_list("id", flat=True))

    assert ids == {story.id}


def test_a_story_with_no_tasks_still_gets_a_column(workspace, project, types):
    """Emptiness is `show_empty_groups`' decision, not this queryset's.

    A story nobody has broken down yet is exactly the row a planning view needs to surface,
    and cycles and modules are listed on the same terms -- all of them, empty or not.
    """
    lonely = _issue(workspace, project, "Unbroken-down story", types["Story"])

    assert lonely.id in set(story_grouping_queryset(workspace.slug, project.id).values_list("id", flat=True))


def test_a_bug_is_a_column_because_level_is_the_whole_rule(workspace, project, types):
    """Bug sits at level 2 with Story, so it is offered too.

    Not an oversight worth an exception: bugs take sub-tasks in practice, and a name-based
    carve-out would break the moment a workspace renamed the type. An empty bug column costs
    one row that `show_empty_groups` already hides.
    """
    bug = _issue(workspace, project, "A defect", types["Bug"])

    assert bug.id in set(story_grouping_queryset(workspace.slug, project.id).values_list("id", flat=True))


def test_group_values_appends_none_for_unparented_work(workspace, project, types):
    story = _issue(workspace, project, "A story", types["Story"])

    values = issue_group_values(field="parent_id", slug=workspace.slug, project_id=str(project.id))

    assert values == [story.id, "None"]


def test_another_project_does_not_leak_columns(workspace, project, types, create_user):
    other = Project.objects.create(name="Other", identifier="OTH", workspace=workspace, created_by=create_user)
    _issue(workspace, other, "Their story", types["Story"])
    ours = _issue(workspace, project, "Our story", types["Story"])

    ids = set(story_grouping_queryset(workspace.slug, project.id).values_list("id", flat=True))

    assert ids == {ours.id}
