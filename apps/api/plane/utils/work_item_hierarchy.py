# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The one rule that keeps the work-item tree from inverting.

`IssueType.level` ranks a type by breadth. This fork seeds Epic at 0, Feature at 1, Story
at 2, Task at 3 and Bug at 2, so **a lower number is a broader type**. Upstream Plane numbers
its two default types the other way round (Task 0, Epic 1); the convention here is the one
the seeded data agrees on, and flipping it would need a data migration to buy nothing.

The rule is that a parent may not be *narrower* than its child:

    parent.level <= child.level

Note it is not strict. Requiring each step to descend a level sounds tidier and is wrong:
the seed parents a Bug (2) to the Story (2) it was found in, which is a real modelling
choice and not an inversion. What actually has to be refused is the inversion itself --
an Epic filed under a Task -- which is exactly what the official behaviour describes when
it says hierarchy enforcement "prevents Tasks from containing Epics".

Untyped work items are left alone. A project with work item types switched off has every
`type` null, and every existing tree in such a project predates this rule; refusing to save
those would break projects that were never asked to declare a level.
"""


def hierarchy_violation(parent, child_type):
    """The reason this parent cannot hold this child, or None when it can.

    `parent` is the prospective parent `Issue` and `child_type` the child's `IssueType`.
    Both may be None, in which case there is no level to compare and nothing to refuse.
    """
    if parent is None or child_type is None:
        return None
    parent_type = getattr(parent, "type", None)
    if parent_type is None:
        return None
    if parent_type.level <= child_type.level:
        return None
    return (
        f"A {parent_type.name} cannot be the parent of a {child_type.name}. "
        f"{child_type.name} is the broader work item type, so the relationship is inverted."
    )
