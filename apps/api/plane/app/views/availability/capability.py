# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""What the availability surface can currently do.

Each flag is false until the slice that implements it lands, and the client renders an
empty state for anything false rather than a dead control. That is the whole reason this
endpoint exists ahead of the feature: it lets the navigation entry, the route and the
three tabs ship and be exercised before a single migration is written, which is what
`testing-platform-workflow.md` §12 asks for.

Flipping a flag is therefore part of the slice that earns it -- see
`docs/planning/team-calendar-wbs.md` for which slice owns which flag.
"""

from rest_framework.response import Response

from plane.app.views.base import BaseAPIView

from .permissions import WorkspaceAvailabilityPermission


class AvailabilityCapabilityEndpoint(BaseAPIView):
    """Expose the team-calendar surface supported by this fork."""

    permission_classes = [WorkspaceAvailabilityPermission]

    def get(self, request, slug):
        return Response(
            {
                "enabled": True,
                "stage": "allocation-and-capacity",
                "capabilities": {
                    # WBS 2 -- reachable hours and the common-slot finder
                    "schedule": True,
                    "overlap": True,
                    # WBS 3 -- leave and team events
                    "leave": True,
                    # WBS 5 -- allocation matrix and cycle capacity
                    "allocation": True,
                    "capacity": True,
                },
            }
        )
