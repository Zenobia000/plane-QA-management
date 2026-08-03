# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Names for the columns the work-item list builds when it groups by parent.

Every other grouping dimension names itself from something the client already holds: states,
cycles, modules and members are all small sets fetched once when a project opens, so the list
can render a column heading without asking anything further. Parents are work items, and the
client holds only the page of work items it is currently showing -- which, with `leaf_only`
on, is precisely the set that excludes the parents. Hence an endpoint.

It returns identity, not state. A column heading needs a name and an identifier to be
clickable, and nothing else; the counts already arrive with the grouped page, and the parent's
own progress is a roll-up the list has no business recomputing per heading.

The queryset is `story_grouping_queryset`, the same one that decides which groups the
paginator opens. Sharing it is the point -- a heading with no group behind it, or a group with
no heading, are both states a second definition would eventually produce.
"""

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import ProjectEntityPermission
from plane.app.views.base import BaseAPIView
from plane.utils.grouper import story_grouping_queryset


class WorkItemParentGroupOptionsEndpoint(BaseAPIView):
    """The stories a project can group its work items by."""

    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        stories = (
            story_grouping_queryset(slug, project_id)
            .order_by("sequence_id")
            .values("id", "name", "sequence_id", "type_id")
        )
        return Response(list(stories), status=status.HTTP_200_OK)
