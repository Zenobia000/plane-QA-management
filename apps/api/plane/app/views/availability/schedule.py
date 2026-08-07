# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Who is reachable when, and when several people are reachable at once.

Both endpoints are derived reads: they own no rows and accept no writes. Instants go out as
UTC ISO-8601 and the client renders them in whichever zone the viewer picked, which is the
only arrangement where a shared axis means the same thing to everyone looking at it.
"""

from datetime import datetime

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from plane.app.serializers import OverlapRequestSerializer
from plane.app.views.base import BaseAPIView
from plane.availability import common_windows, validate_range, workspace_schedule
from plane.db.models import Workspace

from .permissions import WorkspaceAvailabilityPermission


def _window(window):
    return {
        "start": window.start.isoformat(),
        "end": window.end.isoformat(),
        "minutes": window.minutes,
    }


def _schedule(entry):
    return {
        "member_id": entry.member_id,
        "timezone": entry.timezone,
        "calendar_id": entry.calendar_id,
        "hours_per_day": entry.hours_per_day,
        "working": [_window(w) for w in entry.working],
        "core": [_window(w) for w in entry.core],
    }


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"'{value}' is not a date in YYYY-MM-DD form.")


class AvailabilityScheduleEndpoint(BaseAPIView):
    """Every member's declared windows over a date range."""

    permission_classes = [WorkspaceAvailabilityPermission]

    def get(self, request, slug):
        workspace = get_object_or_404(Workspace, slug=slug)
        try:
            start = _parse_date(request.GET.get("from"))
            end = _parse_date(request.GET.get("to"))
            validate_range(start, end)
        except ValueError as error:
            return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        member_ids = [value for value in request.GET.get("member_ids", "").split(",") if value]
        schedules = workspace_schedule(workspace=workspace, start=start, end=end, member_ids=member_ids or None)

        return Response(
            {
                "from": start.isoformat(),
                "to": end.isoformat(),
                "members": [_schedule(entry) for entry in schedules],
            }
        )


class AvailabilityOverlapEndpoint(BaseAPIView):
    """When a named group is reachable together.

    POST rather than GET because the member list is the request body's whole point and a
    query string of twenty UUIDs is not a URL anyone can read or a length every proxy will
    carry. Nothing is written.
    """

    permission_classes = [WorkspaceAvailabilityPermission]

    def post(self, request, slug):
        workspace = get_object_or_404(Workspace, slug=slug)
        payload = OverlapRequestSerializer(data=request.data)
        if not payload.is_valid():
            return Response(payload.errors, status=status.HTTP_400_BAD_REQUEST)

        data = payload.validated_data
        try:
            validate_range(data["date_from"], data["date_to"])
        except ValueError as error:
            return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        schedules = workspace_schedule(
            workspace=workspace,
            start=data["date_from"],
            end=data["date_to"],
            member_ids=[str(value) for value in data["member_ids"]],
        )

        # A requested member with no profile has declared nothing, so folding them in would
        # empty every result with no explanation. Named back instead.
        missing = {str(value) for value in data["member_ids"]} - {entry.member_id for entry in schedules}
        # `working` is empty for two different reasons -- never declared any hours, or away
        # for the whole range -- and the caller needs them apart. Reporting somebody on leave
        # as "hasn't declared any hours" sends the reader to fix a settings problem that does
        # not exist. `hours_per_day` is zero only when there is no profile at all.
        undeclared = [entry.member_id for entry in schedules if not entry.working and not entry.hours_per_day]

        result = common_windows(schedules, minimum_minutes=data["duration_minutes"])

        return Response(
            {
                "duration_minutes": data["duration_minutes"],
                "core": [_window(w) for w in result["core"]],
                "working": [_window(w) for w in result["working"]],
                "unknown_members": sorted(missing),
                "members_without_hours": sorted(undeclared),
            }
        )
