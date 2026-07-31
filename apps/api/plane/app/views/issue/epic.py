# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Epic analytics: how the work underneath an epic is spread across state groups.

An epic row carries only its own fields, and its own state is whatever someone set by hand.
"How is this epic doing" is therefore a question about its descendants, which is what this
endpoint answers and what `TEpicAnalytics` on the client is shaped to receive.

**All descendants, not just direct children.** An epic's children are frequently features,
and a feature's state says nothing about the stories underneath it. Counting only one level
would report an epic as unstarted while every story below it was complete. The walk goes to
the bottom of the subtree.

**The epic itself is excluded.** It is a summary of the work it contains, so counting it
alongside that work states one fact twice and shifts every ratio by one.

Overdue is counted only for work that is still open. A completed or cancelled item whose
target date has passed was finished or dropped, not missed, and colouring it red would
misreport a delivered epic as late.

One query, then an in-memory descent. Walking the tree with a query per node would be an
N+1 against a structure that is read as a whole, and the whole project's rows are needed to
resolve parentage regardless of where the walk stops.
"""

# Python imports
from collections import defaultdict

# Django imports
from django.utils import timezone

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import ProjectEntityPermission
from plane.app.views.base import BaseAPIView
from plane.db.models import Issue

STATE_GROUPS = ("backlog", "unstarted", "started", "completed", "cancelled")

# Work still in flight. Only these can be overdue.
OPEN_STATE_GROUPS = frozenset(("backlog", "unstarted", "started"))


class EpicAnalyticsEndpoint(BaseAPIView):
    """State-group distribution of every work item beneath one epic."""

    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id, epic_id):
        rows = Issue.issue_objects.filter(project_id=project_id, workspace__slug=slug).values_list(
            "id", "parent_id", "state__group", "target_date"
        )

        children = defaultdict(list)
        state_of = {}
        target_of = {}
        for issue_id, parent_id, state_group, target_date in rows:
            state_of[issue_id] = state_group
            target_of[issue_id] = target_date
            if parent_id is not None:
                children[parent_id].append(issue_id)

        if epic_id not in state_of:
            return Response({"error": "Epic not found"}, status=status.HTTP_404_NOT_FOUND)

        counts = {f"{group}_issues": 0 for group in STATE_GROUPS}
        counts["overdue_issues"] = 0
        today = timezone.now().date()

        # Iterative rather than recursive: the depth is user data, and `seen` guards a parent
        # cycle. The write paths refuse to create one, but this endpoint reads rows it did not
        # write and a cycle here would hang the request rather than return a wrong number.
        seen = {epic_id}
        stack = list(children[epic_id])
        while stack:
            node_id = stack.pop()
            if node_id in seen:
                continue
            seen.add(node_id)
            stack.extend(children[node_id])

            state_group = state_of.get(node_id)
            if state_group in STATE_GROUPS:
                counts[f"{state_group}_issues"] += 1

            target_date = target_of.get(node_id)
            if target_date and target_date < today and state_group in OPEN_STATE_GROUPS:
                counts["overdue_issues"] += 1

        return Response(counts, status=status.HTTP_200_OK)
