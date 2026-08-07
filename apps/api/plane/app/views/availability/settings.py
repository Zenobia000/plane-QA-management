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
    CalendarDayBulkSerializer,
    CalendarDaySerializer,
    MemberWorkProfileSerializer,
    MemberWorkProfileWriteSerializer,
    WorkCalendarPatchSerializer,
    WorkCalendarSerializer,
    WorkCalendarWriteSerializer,
)
from plane.app.views.base import BaseAPIView
from plane.availability import (
    UNSET,
    create_work_calendar,
    set_calendar_days,
    update_work_calendar,
    upsert_work_profile,
)
from plane.db.models import (
    CalendarDay,
    MemberWorkProfile,
    User,
    WorkCalendar,
    Workspace,
    WorkspaceMember,
)

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
        # `pop(..., UNSET)` keeps "field absent" apart from "field explicitly null"; the
        # serializer allows null on all three precisely so they can be withdrawn.
        calendar_id = data.pop("work_calendar", UNSET)
        approver_id = data.pop("approver", UNSET)

        calendar = UNSET if calendar_id is UNSET else None
        if calendar_id is not UNSET and calendar_id is not None:
            calendar = WorkCalendar.objects.filter(workspace=workspace, id=calendar_id).first()
            if calendar is None:
                return Response(
                    {"error": "No such work calendar in this workspace."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        approver = UNSET if approver_id is UNSET else None
        if approver_id is not UNSET and approver_id is not None:
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


class WorkCalendarDetailEndpoint(BaseAPIView):
    """Edit or retire one calendar.

    Deleting is refused while members are still bound to it. Silently orphaning them onto
    the workspace default would move somebody's working days without anyone deciding to.
    """

    permission_classes = [WorkspaceAvailabilityPermission]

    def patch(self, request, slug, calendar_id):
        if not _is_admin(request.user, slug):
            return Response(
                {"error": "Only a workspace admin can change a work calendar."},
                status=status.HTTP_403_FORBIDDEN,
            )
        calendar = get_object_or_404(WorkCalendar, workspace__slug=slug, id=calendar_id)
        payload = WorkCalendarPatchSerializer(data=request.data)
        if not payload.is_valid():
            return Response(payload.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            calendar = update_work_calendar(calendar=calendar, **payload.validated_data)
        except ValidationError as error:
            return Response({"error": error.messages}, status=status.HTTP_400_BAD_REQUEST)
        return Response(WorkCalendarSerializer(calendar).data)

    def delete(self, request, slug, calendar_id):
        if not _is_admin(request.user, slug):
            return Response(
                {"error": "Only a workspace admin can delete a work calendar."},
                status=status.HTTP_403_FORBIDDEN,
            )
        calendar = get_object_or_404(WorkCalendar, workspace__slug=slug, id=calendar_id)

        bound = MemberWorkProfile.objects.filter(work_calendar=calendar).count()
        if bound:
            return Response(
                {
                    "error": (
                        f"{bound} member(s) still use this calendar. "
                        "Move them to another one first — deleting it would change their "
                        "working days without anyone choosing to."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        # `work_calendar` is nullable and means "the workspace default", so counting explicit
        # assignments misses everyone who never picked one -- which is most people. Deleting
        # the default would drop them to a bare Mon-Fri mask with no holidays at all, which is
        # exactly the harm the check above exists to prevent, just harder to see.
        if calendar.is_default:
            implicit = (
                WorkspaceMember.objects.filter(workspace=calendar.workspace, is_active=True).count()
                - MemberWorkProfile.objects.filter(
                    workspace=calendar.workspace, work_calendar__isnull=False
                ).count()
            )
            if implicit > 0:
                return Response(
                    {
                        "error": (
                            f"This is the workspace default, so {implicit} member(s) rely on it "
                            "without having chosen it. Make another calendar the default first — "
                            "deleting this one would leave them with no holidays at all."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        calendar.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CalendarDayEndpoint(BaseAPIView):
    """The holidays and make-up workdays of one calendar.

    This is the path that was missing: without it, `MAKEUP_WORKDAY` -- the whole reason the
    model can express a Saturday everyone works -- could only be written by the seed command,
    so nobody could enter this year's published list by hand.
    """

    permission_classes = [WorkspaceAvailabilityPermission]

    def get(self, request, slug, calendar_id):
        calendar = get_object_or_404(WorkCalendar, workspace__slug=slug, id=calendar_id)
        days = calendar.days.all()
        year = request.GET.get("year")
        if year:
            if not year.isdigit():
                return Response({"error": "year must be a number."}, status=status.HTTP_400_BAD_REQUEST)
            days = days.filter(date__year=int(year))
        return Response(CalendarDaySerializer(days, many=True).data)

    def post(self, request, slug, calendar_id):
        if not _is_admin(request.user, slug):
            return Response(
                {"error": "Only a workspace admin can set holidays."}, status=status.HTTP_403_FORBIDDEN
            )
        calendar = get_object_or_404(WorkCalendar, workspace__slug=slug, id=calendar_id)
        payload = CalendarDayBulkSerializer(data=request.data)
        if not payload.is_valid():
            return Response(payload.errors, status=status.HTTP_400_BAD_REQUEST)

        data = payload.validated_data
        try:
            written = set_calendar_days(
                calendar=calendar, days=data["days"], replace_year=data.get("replace_year")
            )
        except ValidationError as error:
            return Response({"error": error.messages}, status=status.HTTP_400_BAD_REQUEST)
        return Response(CalendarDaySerializer(written, many=True).data, status=status.HTTP_201_CREATED)


class CalendarDayDetailEndpoint(BaseAPIView):
    permission_classes = [WorkspaceAvailabilityPermission]

    def delete(self, request, slug, calendar_id, day_id):
        if not _is_admin(request.user, slug):
            return Response(
                {"error": "Only a workspace admin can remove a holiday."}, status=status.HTTP_403_FORBIDDEN
            )
        day = get_object_or_404(CalendarDay, calendar__workspace__slug=slug, calendar_id=calendar_id, id=day_id)
        day.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
