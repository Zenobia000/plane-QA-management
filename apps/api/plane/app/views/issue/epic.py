# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The requirement hierarchy, with every aggregate rolled up to the level that owns it.

The work-item list is a flat projection: hierarchy lives in `parent`, and a parent row
carries only its own fields. That is fine for operating on one item and useless for asking
"how is this epic doing", because the answer is a property of the descendants, not of the
epic row. Every number below is therefore computed downward from each node.

**Nothing here is Epic-specific.** An epic is an ordinary work item whose type carries
`is_epic`; the hierarchy it sits at the top of is the same `parent` chain every other item
uses. So the question "how is this doing" is asked of a node, not of an epic, and the
endpoint takes an optional work-item id to say which node. Asking without one returns every
root, which is what the Epics page wants; asking with one returns that item's own subtree,
which is what a feature or a story wants. The two answers are the same shape because they
are the same computation -- restricting the endpoint to epics would have forced a second
one the first time a feature needed the same numbers.

**A node's rollup describes its leaf descendants, and never itself.** That rule is doing
more work than it looks. A feature's state is a hand-set summary of the same work its
stories represent, so counting the feature alongside its own stories states one fact twice.
An earlier version of this module summed every node in the subtree and consequently
reported an epic with eight stories as 3/11 rather than 3/8, counted two features and the
epic itself as "unsized work", and turned a feature whose two stories both lack contracts
into three uncovered requirements instead of two. All three were the same error.

Leaves are the unit because they are the only nodes that are not summaries of something
else. The known limitation: leaves need not sit at a uniform depth. Break one story into
tasks and leave its siblings whole, and that story's tasks each count once while its
siblings count once apiece -- the denominators stop being comparable. Uniform breakdown
depth is a modelling discipline this endpoint reports on but cannot enforce.

Four aggregates, deliberately from four different axes:

- **state distribution** counts leaves by state group, which is progress at the level the
  work actually happens
- **points** sum the `value` of each leaf's estimate, not the `key`. `key` is a 1-based
  ordinal, so summing it -- which is what the cycle burndown does -- orders sprints
  correctly while not being a point total. A parent's own estimate is ignored once it has
  children, because the breakdown supersedes it
- **coverage** counts leaves using `requirement_coverage`'s own verdict, so the number here
  and the number the release gate blocks on cannot drift apart
- **cycle, module and milestone spread** show where the leaf work sits. A feature whose
  stories straddle three sprints is a scheduling fact the tree would otherwise hide

Defects are excluded from the tree entirely. They are parentless, so they would otherwise
render as roots beside the epics, and they are evidence rather than requirements. A
consequence worth stating: asking for a defect's subtree reports it as absent, because for
the purpose of this endpoint it is.
"""

# Python imports
from collections import defaultdict

# Django imports
from django.db.models import F, Prefetch

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import ProjectEntityPermission
from plane.app.views.base import BaseAPIView
from plane.app.views.testing.report import requirement_coverage
from plane.db.models import CycleIssue, Issue, ModuleIssue, TestResultIssueLink

STATE_GROUPS = ("backlog", "unstarted", "started", "completed", "cancelled")

# Worst status wins, matching the precedence the coverage report already applies. A node
# nothing has verified sorts last rather than first: "no contract" is reported by the
# coverage counts, and letting it outrank a real failure would bury the failure.
STATUS_PRECEDENCE = {"failed": 0, "blocked": 1, "open": 2, "skipped": 3, "passed": 4, None: 5}


def _empty_rollup():
    return {
        "descendants": 0,
        "leaves": 0,
        "state_distribution": {group: 0 for group in STATE_GROUPS},
        "points": {"total": 0, "sized": 0, "unsized": 0},
        "coverage": {"in_scope": 0, "covered": 0, "uncovered": 0, "latest_status": None},
        "cycles": defaultdict(int),
        "milestones": defaultdict(int),
        "modules": defaultdict(int),
    }


def _merge(into, other):
    into["descendants"] += other["descendants"]
    into["leaves"] += other["leaves"]
    for group in STATE_GROUPS:
        into["state_distribution"][group] += other["state_distribution"][group]
    for key in ("total", "sized", "unsized"):
        into["points"][key] += other["points"][key]
    for key in ("in_scope", "covered", "uncovered"):
        into["coverage"][key] += other["coverage"][key]
    for axis in ("cycles", "milestones", "modules"):
        for name, count in other[axis].items():
            into[axis][name] += count
    into["coverage"]["latest_status"] = min(
        into["coverage"]["latest_status"],
        other["coverage"]["latest_status"],
        key=lambda status: STATUS_PRECEDENCE.get(status, 5),
    )
    return into


def _point_value(issue):
    """The displayed figure, not the ordinal.

    A point set of 1, 2, 3, 5, 8, 13 carries keys 1 through 6, so summing keys reports 15
    for a sprint holding 5 + 8 + 13 rather than 26. Non-numeric scales (categories) have no
    meaningful sum, so they count toward `unsized` instead of silently contributing zero.
    """
    if not issue.estimate_point:
        return None
    try:
        return int(issue.estimate_point.value)
    except (TypeError, ValueError):
        return None


def _leaf_contribution(issue, coverage_row):
    """What one leaf contributes to every ancestor above it.

    Only leaves produce numbers. An interior node's rollup is the sum of these and nothing
    else, which is what keeps a summary from being counted beside the thing it summarises.
    """
    metrics = _empty_rollup()
    metrics["leaves"] = 1

    state_group = issue.state.group if issue.state else None
    if state_group in metrics["state_distribution"]:
        metrics["state_distribution"][state_group] += 1

    points = _point_value(issue)
    if points is None:
        metrics["points"]["unsized"] += 1
    else:
        metrics["points"]["total"] += points
        metrics["points"]["sized"] += 1

    for link in issue.issue_cycle.all():
        metrics["cycles"][link.cycle.name] += 1
    for link in issue.issue_module.all():
        metrics["modules"][link.module.name] += 1
    if issue.milestone:
        metrics["milestones"][issue.milestone.name] += 1

    if coverage_row and coverage_row["requires_contract"]:
        metrics["coverage"]["in_scope"] = 1
        metrics["coverage"]["covered" if coverage_row["covered"] else "uncovered"] = 1
        metrics["coverage"]["latest_status"] = coverage_row["latest_status"]

    return metrics


def _serialize(rollup):
    serialized = dict(rollup)
    for axis in ("cycles", "milestones", "modules"):
        serialized[axis] = [
            {"name": name, "count": count}
            for name, count in sorted(rollup[axis].items(), key=lambda pair: -pair[1])
        ]
    return serialized


def _find_node(nodes, node_id):
    for node in nodes:
        if node["id"] == node_id:
            return node
        found = _find_node(node["children"], node_id)
        if found is not None:
            return found
    return None


def build_hierarchy(project_id, root_id=None):
    """Every root of the project, or the single subtree beneath `root_id`.

    The subtree is located in the finished tree rather than by querying downward from the
    root, so it inherits the cycle guard, the defect exclusion and the coverage join for
    free. A node's rollup already describes only what sits beneath it, so the subtree needs
    no recomputation to be correct in isolation -- it is the same object the full tree holds.
    """
    coverage_by_item = {row["work_item_id"]: row for row in requirement_coverage(project_id)}

    defect_ids = set(
        TestResultIssueLink.objects.filter(project_id=project_id).values_list("issue_id", flat=True)
    )
    issues = list(
        Issue.issue_objects.filter(project_id=project_id)
        .select_related("state", "type", "estimate_point", "milestone")
        .prefetch_related(
            Prefetch("issue_cycle", queryset=CycleIssue.objects.select_related("cycle")),
            Prefetch("issue_module", queryset=ModuleIssue.objects.select_related("module")),
        )
        .annotate(type_level=F("type__level"))
    )

    by_id = {issue.id: issue for issue in issues if issue.id not in defect_ids}
    children = defaultdict(list)
    roots = []
    for issue in by_id.values():
        if issue.parent_id and issue.parent_id in by_id:
            children[issue.parent_id].append(issue)
        else:
            roots.append(issue)

    def node(issue, seen):
        # The schema does not forbid a parent cycle, so the traversal has to.
        if issue.id in seen:
            return None
        seen = seen | {issue.id}

        rendered = []
        for child in sorted(children.get(issue.id, []), key=lambda item: item.sequence_id):
            built = node(child, seen)
            if built is not None:
                rendered.append(built)

        if rendered:
            # An interior node reports its descendants and contributes nothing of its own.
            rollup = _empty_rollup()
            for built in rendered:
                _merge(rollup, built["_contribution"])
                rollup["descendants"] += 1
            contribution = rollup
        else:
            # A leaf has nothing beneath it, so its own rollup is empty; the numbers it
            # produces belong to its ancestors.
            rollup = _empty_rollup()
            contribution = _leaf_contribution(issue, coverage_by_item.get(str(issue.id)))

        row = coverage_by_item.get(str(issue.id))
        return {
            "id": str(issue.id),
            "sequence_id": issue.sequence_id,
            "name": issue.name,
            "priority": issue.priority,
            "is_leaf": not rendered,
            "type": (
                {"id": str(issue.type_id), "name": issue.type.name, "is_epic": issue.type.is_epic}
                if issue.type
                else None
            ),
            "state": (
                {"id": str(issue.state_id), "name": issue.state.name, "group": issue.state.group}
                if issue.state
                else None
            ),
            "estimate_point": _point_value(issue),
            "milestone": issue.milestone.name if issue.milestone else None,
            # The node's own verdict, distinct from the rollup: an epic is "covered" when
            # anything beneath it is, which is a different statement from how many of its
            # leaves hold contracts.
            "covered": bool(row and row["covered"]),
            "latest_status": row["latest_status"] if row else None,
            "children": rendered,
            "rollup": _serialize(rollup),
            "_contribution": contribution,
        }

    def strip(built):
        built.pop("_contribution", None)
        for child in built["children"]:
            strip(child)
        return built

    ordered = sorted(
        roots, key=lambda item: (item.type_level if item.type_level is not None else 99, item.sequence_id)
    )
    nodes = [strip(built) for built in (node(issue, frozenset()) for issue in ordered) if built]

    if root_id is None:
        return nodes
    found = _find_node(nodes, str(root_id))
    return [found] if found is not None else []


class WorkItemHierarchyEndpoint(BaseAPIView):
    """The hierarchy beneath a work item, or beneath every root when none is named.

    Registered at two URLs. `/epic-hierarchy/` is the older spelling and is kept because
    callers exist; it is the no-root form and nothing about it is Epic-specific.
    """

    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id, issue_id=None):
        nodes = build_hierarchy(project_id, root_id=issue_id)
        if issue_id is not None and not nodes:
            return Response(
                {"error": "The work item does not exist in this project's hierarchy."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"nodes": nodes})


# The name the URL conf and `views/__init__` imported before the endpoint stopped being
# about epics. Same view, same behaviour when no work item is named.
ProjectEpicHierarchyEndpoint = WorkItemHierarchyEndpoint
