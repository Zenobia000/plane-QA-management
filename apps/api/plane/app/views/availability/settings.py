# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Work calendars and per-member working shapes.

Writes go through `plane.availability.services`, never straight to the ORM, so the model's
own `clean()` runs once for every caller rather than once per view.
"""

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from plane.app.serializers import (
    MemberWorkProfileSerializer,
    MemberWorkProfileWriteSerializer,
    WorkCalendarSerializer,
    WorkCalendarWriteSerializer,
)
from plane.app.views.base import BaseAPIView
from plane.availability import create_work_calendar, upsert_work_profile
from plane.db.models import MemberWorkProfile, User, WorkCalendar, Workspace, WorkspaceMember

from .permissions import ADMIN, WorkspaceAvailabilityPermission


def _is_admin(user, slug):
    return WorkspaceMember.objects.filter(
        member=user, workspace__slug=slug, role=ADMIN, is_active=True
    ).exists()


class WorkCalendarListCreateEndpoint(BaseAPIView):
    permission_classes = [WorkspaceAvailabilityPermission]

    def get(self, request, slug):
        calendars = WorkCalendar.objects.filter(workspace__slug=slug)
        return Response(WorkCalendarSerializer(calendars, many=True).data)

    def post(self, request, slug):
        if not _is_admin(request.user, slug):
            return Response(
                {"error": "Only a workspace admin can define a work calendar."},
                status=status.HTTP_403_FORBIDDEN,
            )
        payload = WorkCalendarWriteSerializer(data=request.data)
        if not payload.is_valid():
            return Response(payload.errors, status=status.HTTP_400_BAD_REQUEST)

        workspace = get_object_or_404(Workspace, slug=slug)
        try:
            calendar = create_work_calendar(workspace=workspace, **payload.validated_data)
        except ValidationError as error:
            return Response({"error": error.messages}, status=status.HTTP_400_BAD_REQUEST)
        return Response(WorkCalendarSerializer(calendar).data, status=status.HTTP_201_CREATED)


class MemberWorkProfileListEndpoint(BaseAPIView):
    permission_classes = [WorkspaceAvailabilityPermission]

    def get(self, request, slug):
        profiles = MemberWorkProfile.objects.filter(workspace__slug=slug)
        return Response(MemberWorkProfileSerializer(profiles, many=True).data)


class MemberWorkProfileDetailEndpoint(BaseAPIView):
    """One member's declared shape.

    Anyone in the workspace may read it -- the point of the surface is that colleagues can
    see when you are reachable. Only the member themself or an admin may write it, because
    a declaration somebody else made on your behalf is not a declaration.
    """

    permission_classes = [WorkspaceAvailabilityPermission]

    def get(self, request, slug, member_id):
        profile = MemberWorkProfile.objects.filter(workspace__slug=slug, member_id=member_id).first()
        if profile is None:
            return Response({"member": str(member_id), "declared": False}, status=status.HTTP_200_OK)
        return Response(MemberWorkProfileSerializer(profile).data)

    def patch(self, request, slug, member_id):
        if str(request.user.id) != str(member_id) and not _is_admin(request.user, slug):
            return Response(
                {"error": "Only this member or a workspace admin can change these hours."},
                status=status.HTTP_403_FORBIDDEN,
            )

        payload = MemberWorkProfileWriteSerializer(data=request.data)
        if not payload.is_valid():
            return Response(payload.errors, status=status.HTTP_400_BAD_REQUEST)

        workspace = get_object_or_404(Workspace, slug=slug)
        membership = WorkspaceMember.objects.filter(
            workspace=workspace, member_id=member_id, is_active=True
        ).first()
        if membership is None:
            return Response(
                {"error": "That member is not active in this workspace."},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = dict(payload.validated_data)
        calendar_id = data.pop("work_calendar", None)
        approver_id = data.pop("approver", None)

        calendar = None
        if calendar_id is not None:
            calendar = WorkCalendar.objects.filter(workspace=workspace, id=calendar_id).first()
            if calendar is None:
                return Response(
                    {"error": "No such work calendar in this workspace."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        approver = None
        if approver_id is not None:
            # An approver outside the workspace could never act on the request, so a
            # pointer at one is a silent dead end rather than a configuration.
            if not WorkspaceMember.objects.filter(
                workspace=workspace, member_id=approver_id, is_active=True
            ).exists():
                return Response(
                    {"error": "An approver must be an active member of this workspace."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            approver = User.objects.get(id=approver_id)

        try:
            profile = upsert_work_profile(
                workspace=workspace,
                member=membership.member,
                work_calendar=calendar,
                approver=approver,
                **data,
            )
        except ValidationError as error:
            return Response({"error": error.messages}, status=status.HTTP_400_BAD_REQUEST)

        return Response(MemberWorkProfileSerializer(profile).data)
