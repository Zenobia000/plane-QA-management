# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""How one person's time is split across projects, and what a cycle therefore has.

Reading is open to the workspace; writing is ADMIN only. An allocation is a promise made
about somebody's week by whoever runs the plan, not a claim they make about themselves --
the opposite of the work profile, which only the member may set.
"""

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ProjectEntityPermission
from plane.app.views.base import BaseAPIView
from plane.availability import cycle_capacity, set_allocation
from plane.db.models import (
    Cycle,
    MemberProjectAllocation,
    Project,
    Workspace,
    WorkspaceMember,
)

from .permissions import ADMIN, WorkspaceAvailabilityPermission


class AllocationMatrixEndpoint(BaseAPIView):
    permission_classes = [WorkspaceAvailabilityPermission]

    def get(self, request, slug):
        rows = MemberProjectAllocation.objects.filter(workspace__slug=slug)
        totals: dict[str, int] = {}
        payload = []
        for row in rows:
            member_id = str(row.member_id)
            totals[member_id] = totals.get(member_id, 0) + row.allocation_percent
            payload.append(
                {
                    "member_id": member_id,
                    "project_id": str(row.project_id),
                    "allocation_percent": row.allocation_percent,
                }
            )
        return Response({"allocations": payload, "totals": totals})

    def put(self, request, slug):
        if not WorkspaceMember.objects.filter(
            member=request.user, workspace__slug=slug, role=ADMIN, is_active=True
        ).exists():
            return Response(
                {"error": "Only a workspace admin can allocate someone's time."},
                status=status.HTTP_403_FORBIDDEN,
            )

        workspace = get_object_or_404(Workspace, slug=slug)
        member_id = request.data.get("member_id")
        project_id = request.data.get("project_id")
        percent = request.data.get("allocation_percent")

        if member_id is None or project_id is None or percent is None:
            return Response(
                {"error": "member_id, project_id and allocation_percent are all required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership = WorkspaceMember.objects.filter(
            workspace=workspace, member_id=member_id, is_active=True
        ).select_related("member").first()
        if membership is None:
            return Response(
                {"error": "That member is not active in this workspace."}, status=status.HTTP_404_NOT_FOUND
            )

        project = Project.objects.filter(workspace=workspace, id=project_id).first()
        if project is None:
            return Response({"error": "No such project in this workspace."}, status=status.HTTP_404_NOT_FOUND)

        try:
            allocation = set_allocation(
                workspace=workspace, member=membership.member, project=project, percent=int(percent)
            )
        except (ValidationError, ValueError) as error:
            messages = error.messages if isinstance(error, ValidationError) else [str(error)]
            return Response({"error": messages}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "member_id": str(membership.member_id),
                "project_id": str(project.id),
                "allocation_percent": allocation.allocation_percent if allocation else 0,
            }
        )


class CycleCapacityEndpoint(BaseAPIView):
    """Available hours for one cycle, per member.

    Project-scoped, unlike the rest of this module: a cycle belongs to a project, and the
    question here is what *this* project has, after everyone's other commitments.
    """

    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id, cycle_id):
        cycle = get_object_or_404(
            Cycle.objects.select_related("project", "project__workspace"),
            workspace__slug=slug,
            project_id=project_id,
            id=cycle_id,
        )
        return Response(cycle_capacity(cycle=cycle))
