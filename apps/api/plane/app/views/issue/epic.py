# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The requirement hierarchy, with every aggregate rolled up to the level that owns it.

The work-item list is a flat projection: hierarchy lives in `parent`, and a parent row
carries only its own fields. That is fine for operating on one item and useless for asking
"how is this epic doing", because the answer is a property of the descendants, not of the
epic row. Every number below is therefore computed downward from each node.

Four aggregates, deliberately from four different axes:

- **state distribution** walks the breakdown. The one-level `state_distribution` the
  sub-issues endpoint already returns is not enough here -- an epic's children are
  features, and their states say nothing about the ten stories underneath
- **points** sum the `value` of each descendant's estimate, not the `key`. `key` is a
  1-based ordinal, so summing it -- which is what the cycle burndown does -- orders
  sprints correctly while not being a point total
- **coverage** is taken straight from `requirement_coverage`, which already walks the same
  tree, excludes defects and resolves the worst status. Recomputing it here would be a
  second definition of the same word, and the two would drift
- **cycle and milestone spread** show where the work underneath actually sits. A feature
  whose stories straddle three sprints is a scheduling fact the tree would otherwise hide

Defects are excluded from the tree entirely. They are parentless, so they would otherwise
render as roots beside the epics, and they are evidence rather than requirements.
"""

# Python imports
from collections import defaultdict

# Django imports
from django.db.models import F, Prefetch

# Third party imports
from rest_framework.response import Response

# Module imports
from plane.app.permissions import ProjectEntityPermission
from plane.app.views.base import BaseAPIView
from plane.app.views.testing.report import requirement_coverage
from plane.db.models import CycleIssue, Issue, ModuleIssue, TestResultIssueLink

STATE_GROUPS = ("backlog", "unstarted", "started", "completed", "cancelled")


def _empty_rollup():
    return {
        "descendants": 0,
        "state_distribution": {group: 0 for group in STATE_GROUPS},
        "points": {"total": 0, "sized": 0, "unsized": 0},
        "coverage": {"in_scope": 0, "covered": 0, "uncovered": 0, "latest_status": None},
        "cycles": defaultdict(int),
        "milestones": defaultdict(int),
        "modules": defaultdict(int),
    }


def _merge(into, other):
    into["descendants"] += other["descendants"]
    for group in STATE_GROUPS:
        into["state_distribution"][group] += other["state_distribution"][group]
    for key in ("total", "sized", "unsized"):
        into["points"][key] += other["points"][key]
    for key in ("in_scope", "covered", "uncovered"):
        into["coverage"][key] += other["coverage"][key]
    for axis in ("cycles", "milestones", "modules"):
        for name, count in other[axis].items():
            into[axis][name] += count
    return into


# Worst status wins, matching the precedence the coverage report already applies.
STATUS_PRECEDENCE = {"failed": 0, "blocked": 1, "open": 2, "skipped": 3, "passed": 4, None: 5}


def _worst(left, right):
    return min(left, right, key=lambda status: STATUS_PRECEDENCE.get(status, 5))


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


def build_hierarchy(project_id):
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

        own = _empty_rollup()
        own["descendants"] = 1
        state_group = issue.state.group if issue.state else None
        if state_group in own["state_distribution"]:
            own["state_distribution"][state_group] += 1
        points = _point_value(issue)
        if points is None:
            own["points"]["unsized"] += 1
        else:
            own["points"]["total"] += points
            own["points"]["sized"] += 1
        for link in issue.issue_cycle.all():
            own["cycles"][link.cycle.name] += 1
        for link in issue.issue_module.all():
            own["modules"][link.module.name] += 1
        if issue.milestone:
            own["milestones"][issue.milestone.name] += 1

        row = coverage_by_item.get(str(issue.id))
        worst = None
        if row and row["requires_contract"]:
            own["coverage"]["in_scope"] = 1
            own["coverage"]["covered" if row["covered"] else "uncovered"] = 1
            worst = row["latest_status"]

        rollup = _empty_rollup()
        _merge(rollup, own)
        rendered = []
        for child in sorted(children.get(issue.id, []), key=lambda item: item.sequence_id):
            built = node(child, seen)
            if built is None:
                continue
            rendered.append(built)
            _merge(rollup, built["_rollup_raw"])
            worst = _worst(worst, built["rollup"]["coverage"]["latest_status"])

        rollup["coverage"]["latest_status"] = worst
        return {
            "id": str(issue.id),
            "sequence_id": issue.sequence_id,
            "name": issue.name,
            "priority": issue.priority,
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
            "children": rendered,
            "rollup": _serialize(rollup),
            "_rollup_raw": rollup,
        }

    def strip(built):
        built.pop("_rollup_raw", None)
        for child in built["children"]:
            strip(child)
        return built

    ordered = sorted(roots, key=lambda item: (item.type_level if item.type_level is not None else 99, item.sequence_id))
    return [strip(built) for built in (node(issue, frozenset()) for issue in ordered) if built]


def _serialize(rollup):
    serialized = dict(rollup)
    for axis in ("cycles", "milestones", "modules"):
        serialized[axis] = [
            {"name": name, "count": count}
            for name, count in sorted(rollup[axis].items(), key=lambda pair: -pair[1])
        ]
    # The node counts itself, which is not a descendant.
    serialized["descendants"] = max(rollup["descendants"] - 1, 0)
    return serialized


class ProjectEpicHierarchyEndpoint(BaseAPIView):
    """Epic to feature to story, with each level reporting what sits beneath it."""

    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        return Response({"nodes": build_hierarchy(project_id)})
