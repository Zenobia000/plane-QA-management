# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Which work items become columns when the list groups by parent.

The rule is now "it is a parent". It used to be `level == 2`, chosen to bound the output,
and the bound was real but the choice cost more than it saved: the paginator discards rows
whose group is not among these values, so any work item parented outside level 2 was not
shown anywhere. A project running Epic -> Feature -> Story parents every story to a Feature,
and on the instance that reported this, 12 of 14 rows vanished behind 15 empty headings.

Two decisions the old rule made are worth restating, because this rule keeps one and
overturns the other on purpose.

*Kept*: no carve-out by type name. A defect that has sub-tasks is a parent and gets a
column, exactly like a story. Being a parent is a structural fact; "Bug" is a string a
workspace can rename.

*Overturned*: a story with no children no longer gets a column. That was a deliberate
planning aid -- surface the thing nobody has broken down yet -- but it cannot be paid for
with rows that disappear, and it produced the empty screen that surfaced this. Bounding is
still satisfied, and more tightly: parents are a subset of the tree, fewer than the level
rule returned on both projects checked.
"""

import pytest

from plane.db.models import Issue, IssueType, Project, ProjectMember
from plane.utils.grouper import issue_group_values, parent_grouping_queryset


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


def test_every_node_with_children_becomes_a_column(workspace, project, types):
    """The whole chain, which is where the old rule lost rows.

    `level == 2` gave this tree one column -- the story -- so the feature and the epic had
    none, and the two rows that name them as parent were discarded rather than displayed.
    The leaf is correctly absent: nothing can be filed under it.
    """
    epic = _issue(workspace, project, "An epic", types["Epic"])
    feature = _issue(workspace, project, "A feature", types["Feature"], parent=epic)
    story = _issue(workspace, project, "A story", types["Story"], parent=feature)
    task = _issue(workspace, project, "A task", types["Task"], parent=story)

    ids = set(parent_grouping_queryset(workspace.slug, project.id).values_list("id", flat=True))

    assert ids == {epic.id, feature.id, story.id}
    assert task.id not in ids


def test_a_story_with_no_children_gets_no_column(workspace, project, types):
    """Overturns the previous rule, which offered one as a planning prompt.

    A column nothing can ever sit in is only a prompt while the rest of the list is right,
    and under the level rule the rest of the list was not: rows parented elsewhere were
    dropped to make room for these.
    """
    lonely = _issue(workspace, project, "Unbroken-down story", types["Story"])

    assert lonely.id not in set(parent_grouping_queryset(workspace.slug, project.id).values_list("id", flat=True))


def test_a_defect_with_sub_tasks_is_a_column(workspace, project, types):
    """The old rule's better half, kept.

    Bugs take sub-tasks in practice, and excluding them by name would break the moment a
    workspace renamed the type. Nothing here reads a type at all -- a parent is a parent.
    """
    bug = _issue(workspace, project, "A defect", types["Bug"])
    child = _issue(workspace, project, "Fix the thing", types["Task"])
    child.parent = bug
    child.save()

    assert bug.id in set(parent_grouping_queryset(workspace.slug, project.id).values_list("id", flat=True))


def test_a_parent_at_any_level_gets_a_column(workspace, project, types):
    """The regression. A Feature parenting a Story is the shape that lost 12 rows."""
    feature = _issue(workspace, project, "Export", types["Feature"])
    story = _issue(workspace, project, "Export as CSV", types["Story"])
    story.parent = feature
    story.save()

    columns = set(parent_grouping_queryset(workspace.slug, project.id).values_list("id", flat=True))

    assert feature.id in columns
    # And the row that names it can therefore be placed instead of discarded.
    assert str(feature.id) in [str(v) for v in issue_group_values("parent_id", workspace.slug, str(project.id))]


def test_group_values_appends_none_for_unparented_work(workspace, project, types):
    parent = _issue(workspace, project, "A story", types["Story"])
    child = _issue(workspace, project, "Its task", types["Task"])
    child.parent = parent
    child.save()

    values = issue_group_values(field="parent_id", slug=workspace.slug, project_id=str(project.id))

    assert values == [parent.id, "None"]


def test_another_project_does_not_leak_columns(workspace, project, types, create_user):
    other = Project.objects.create(name="Other", identifier="OTH", workspace=workspace, created_by=create_user)
    their_parent = _issue(workspace, other, "Their story", types["Story"])
    their_child = _issue(workspace, other, "Their task", types["Task"])
    their_child.parent = their_parent
    their_child.save()
    ours = _issue(workspace, project, "Our story", types["Story"])
    our_child = _issue(workspace, project, "Our task", types["Task"])
    our_child.parent = ours
    our_child.save()

    ids = set(parent_grouping_queryset(workspace.slug, project.id).values_list("id", flat=True))

    assert ids == {ours.id}
