# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Absences and team events.

The visibility rule is the part worth reading. A colleague may see *that* someone is away
and what kind of absence it is; the reason and any decision note are held back unless the
reader is the member, their resolved approver, or a workspace admin. Enforced in the
serializer via `may_read_reason`, because a field the API returns is public regardless of
which client chooses not to render it.
"""

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from plane.app.serializers import (
    LeaveTypePatchSerializer,
    LeaveTypeSerializer,
    LeaveTypeWriteSerializer,
    MemberLeaveSerializer,
    MemberLeaveWriteSerializer,
    TeamEventSerializer,
    TeamEventWriteSerializer,
)
from plane.app.views.base import BaseAPIView
from plane.availability import (
    NotTheApprover,
    cancel_leave,
    create_leave,
    create_team_event,
    decide_leave,
    pending_for,
    validate_range,
)
from plane.db.models import (
    LeaveStatus,
    LeaveType,
    MemberLeave,
    MemberWorkProfile,
    Project,
    TeamEvent,
    Workspace,
    WorkspaceMember,
)

from .permissions import ADMIN, WorkspaceAvailabilityPermission
from .schedule import _parse_date


def _is_admin(user, slug):
    return WorkspaceMember.objects.filter(member=user, workspace__slug=slug, role=ADMIN, is_active=True).exists()


def reason_visibility(user, slug):
    """A predicate the serializer calls per row.

    Approvers are resolved once, up front: without it every row would trigger a profile
    lookup, and a wallchart is a page of rows.
    """
    admin = _is_admin(user, slug)
    approves_for = set(
        MemberWorkProfile.objects.filter(workspace__slug=slug, approver=user).values_list("member_id", flat=True)
    )

    def may_read(leave):
        return admin or leave.member_id == user.id or leave.member_id in approves_for

    return may_read


class LeaveTypeListCreateEndpoint(BaseAPIView):
    permission_classes = [WorkspaceAvailabilityPermission]

    def get(self, request, slug):
        types = LeaveType.objects.filter(workspace__slug=slug)
        return Response(LeaveTypeSerializer(types, many=True).data)

    def post(self, request, slug):
        if not _is_admin(request.user, slug):
            return Response(
                {"error": "Only a workspace admin can define a leave type."}, status=status.HTTP_403_FORBIDDEN
            )
        payload = LeaveTypeWriteSerializer(data=request.data)
        if not payload.is_valid():
            return Response(payload.errors, status=status.HTTP_400_BAD_REQUEST)

        workspace = get_object_or_404(Workspace, slug=slug)
        leave_type = LeaveType(workspace=workspace, **payload.validated_data)
        try:
            # `workspace` stays in: excluding it also drops the (workspace, name) constraint
            # from validation, which left a duplicate name to be caught by the database
            # instead -- a generic error on a poisoned transaction rather than a named field.
            leave_type.full_clean(exclude=["created_by", "updated_by"])
        except ValidationError as error:
            return Response({"error": error.messages}, status=status.HTTP_400_BAD_REQUEST)
        leave_type.save()
        return Response(LeaveTypeSerializer(leave_type).data, status=status.HTTP_201_CREATED)


class LeaveTypeDetailEndpoint(BaseAPIView):
    """Edit a leave type, or retire it.

    There is no delete. `MemberLeave.leave_type` is PROTECT, and a type that has ever been
    used is part of the record of who was away and why -- removing it would rewrite history
    to tidy a settings list. Setting `is_active` false hides it from the form and leaves
    everything already logged intact.
    """

    permission_classes = [WorkspaceAvailabilityPermission]

    def patch(self, request, slug, type_id):
        if not _is_admin(request.user, slug):
            return Response(
                {"error": "Only a workspace admin can change a leave type."},
                status=status.HTTP_403_FORBIDDEN,
            )
        leave_type = get_object_or_404(LeaveType, workspace__slug=slug, id=type_id)
        payload = LeaveTypePatchSerializer(data=request.data)
        if not payload.is_valid():
            return Response(payload.errors, status=status.HTTP_400_BAD_REQUEST)

        for field, value in payload.validated_data.items():
            setattr(leave_type, field, value)
        try:
            leave_type.full_clean(exclude=["created_by", "updated_by"])
        except ValidationError as error:
            return Response({"error": error.messages}, status=status.HTTP_400_BAD_REQUEST)
        leave_type.save()
        return Response(LeaveTypeSerializer(leave_type).data)


class MemberLeaveListCreateEndpoint(BaseAPIView):
    permission_classes = [WorkspaceAvailabilityPermission]

    def get(self, request, slug):
        try:
            start = _parse_date(request.GET.get("from"))
            end = _parse_date(request.GET.get("to"))
            validate_range(start, end)
        except ValueError as error:
            return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        leaves = MemberLeave.objects.filter(
            workspace__slug=slug, start_date__lte=end, end_date__gte=start
        ).select_related("leave_type")

        member_ids = [value for value in request.GET.get("member_ids", "").split(",") if value]
        if member_ids:
            leaves = leaves.filter(member_id__in=member_ids)
        # Cancelled and rejected rows stay in the table but are not what "who is away"
        # means; a caller that wants them asks for them.
        if request.GET.get("include_closed") != "true":
            leaves = leaves.filter(status__in=[LeaveStatus.PENDING, LeaveStatus.APPROVED])

        serializer = MemberLeaveSerializer(
            leaves, many=True, context={"may_read_reason": reason_visibility(request.user, slug)}
        )
        return Response(serializer.data)

    def post(self, request, slug):
        payload = MemberLeaveWriteSerializer(data=request.data)
        if not payload.is_valid():
            return Response(payload.errors, status=status.HTTP_400_BAD_REQUEST)

        data = dict(payload.validated_data)
        workspace = get_object_or_404(Workspace, slug=slug)

        target_id = data.pop("member", None) or request.user.id
        if str(target_id) != str(request.user.id) and not _is_admin(request.user, slug):
            return Response(
                {"error": "Only a workspace admin can log an absence for someone else."},
                status=status.HTTP_403_FORBIDDEN,
            )

        membership = WorkspaceMember.objects.filter(
            workspace=workspace, member_id=target_id, is_active=True
        ).select_related("member").first()
        if membership is None:
            return Response(
                {"error": "That member is not active in this workspace."}, status=status.HTTP_404_NOT_FOUND
            )

        leave_type = LeaveType.objects.filter(workspace=workspace, id=data.pop("leave_type"), is_active=True).first()
        if leave_type is None:
            return Response(
                {"error": "No such active leave type in this workspace."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            leave = create_leave(workspace=workspace, member=membership.member, leave_type=leave_type, **data)
        except ValidationError as error:
            return Response({"error": error.messages}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            MemberLeaveSerializer(leave, context={"may_read_reason": reason_visibility(request.user, slug)}).data,
            status=status.HTTP_201_CREATED,
        )


class MemberLeaveDetailEndpoint(BaseAPIView):
    permission_classes = [WorkspaceAvailabilityPermission]

    ACTIONS = {"cancel", "approve", "reject"}

    def patch(self, request, slug, leave_id):
        leave = get_object_or_404(MemberLeave, workspace__slug=slug, id=leave_id)
        action = request.data.get("action")

        if action not in self.ACTIONS:
            return Response(
                {"error": f"action must be one of: {', '.join(sorted(self.ACTIONS))}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if action == "cancel":
            if leave.member_id != request.user.id and not _is_admin(request.user, slug):
                return Response(
                    {"error": "Only this member or a workspace admin can cancel it."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            try:
                leave = cancel_leave(leave_id=leave.id, actor=request.user)
            except ValidationError as error:
                return Response({"error": error.messages}, status=status.HTTP_409_CONFLICT)
        else:
            try:
                leave = decide_leave(
                    leave_id=leave.id,
                    actor=request.user,
                    approve=action == "approve",
                    note=request.data.get("note", ""),
                )
            except NotTheApprover:
                return Response(
                    {"error": "You are not the approver for this request."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            except ValidationError as error:
                return Response({"error": error.messages}, status=status.HTTP_409_CONFLICT)

        return Response(
            MemberLeaveSerializer(leave, context={"may_read_reason": reason_visibility(request.user, slug)}).data
        )


class PendingLeaveEndpoint(BaseAPIView):
    """What is waiting on the caller.

    Its own endpoint rather than a filter on the list, because "requests I must decide" is
    a different question from "who is away in August" and answering it needs the approver
    resolution the list has no reason to run.
    """

    permission_classes = [WorkspaceAvailabilityPermission]

    def get(self, request, slug):
        workspace = get_object_or_404(Workspace, slug=slug)
        queue = pending_for(workspace=workspace, actor=request.user).select_related("leave_type")
        return Response(
            MemberLeaveSerializer(
                queue, many=True, context={"may_read_reason": reason_visibility(request.user, slug)}
            ).data
        )


class TeamEventListCreateEndpoint(BaseAPIView):
    permission_classes = [WorkspaceAvailabilityPermission]

    def get(self, request, slug):
        try:
            start = _parse_date(request.GET.get("from"))
            end = _parse_date(request.GET.get("to"))
            validate_range(start, end)
        except ValueError as error:
            return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        events = (
            TeamEvent.objects.filter(workspace__slug=slug, start_date__lte=end, end_date__gte=start)
            .prefetch_related("attendees")
        )
        return Response(TeamEventSerializer(events, many=True).data)

    def post(self, request, slug):
        if not _is_admin(request.user, slug):
            return Response(
                {"error": "Only a workspace admin can create a team event."}, status=status.HTTP_403_FORBIDDEN
            )
        payload = TeamEventWriteSerializer(data=request.data)
        if not payload.is_valid():
            return Response(payload.errors, status=status.HTTP_400_BAD_REQUEST)

        workspace = get_object_or_404(Workspace, slug=slug)
        data = dict(payload.validated_data)
        project_id = data.pop("project", None)
        project = None
        if project_id:
            project = Project.objects.filter(workspace=workspace, id=project_id).first()
            if project is None:
                return Response(
                    {"error": "No such project in this workspace."}, status=status.HTTP_400_BAD_REQUEST
                )

        try:
            event = create_team_event(workspace=workspace, project=project, **data)
        except ValidationError as error:
            return Response({"error": error.messages}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TeamEventSerializer(event).data, status=status.HTTP_201_CREATED)
