# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Read and write shapes for the team calendar.

Read/write split as elsewhere in this fork. Nothing here exposes an observed-activity
field; ADR 0008 bars this surface from `last_active` and a serializer is where such a field
would slip in, since a `fields = "__all__"` on a user relation is all it would take.
"""

from rest_framework import serializers

from plane.db.models import CalendarDay, MemberWorkProfile, WorkCalendar

from .base import BaseSerializer


class CalendarDaySerializer(BaseSerializer):
    class Meta:
        model = CalendarDay
        fields = ["id", "date", "name", "kind"]
        read_only_fields = ["id"]


class WorkCalendarSerializer(BaseSerializer):
    class Meta:
        model = WorkCalendar
        fields = ["id", "name", "timezone", "working_weekdays", "is_default"]
        read_only_fields = ["id"]


class WorkCalendarWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    timezone = serializers.CharField(max_length=255)
    working_weekdays = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=7),
        required=False,
        allow_empty=False,
    )
    is_default = serializers.BooleanField(required=False, default=False)


class MemberWorkProfileSerializer(BaseSerializer):
    class Meta:
        model = MemberWorkProfile
        fields = [
            "id",
            "member",
            "work_calendar",
            "timezone",
            "work_start_time",
            "work_end_time",
            "core_hours_start",
            "core_hours_end",
            "hours_per_day",
            "approver",
        ]
        read_only_fields = ["id", "member"]


class MemberWorkProfileWriteSerializer(serializers.Serializer):
    """Every field optional: a PATCH here is usually one field.

    `clear_core_hours` exists because `None` already means "leave unchanged" for the rest,
    so without it a core-hours commitment could be made but never withdrawn.
    """

    work_calendar = serializers.UUIDField(required=False, allow_null=True)
    timezone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    work_start_time = serializers.TimeField(required=False)
    work_end_time = serializers.TimeField(required=False)
    core_hours_start = serializers.TimeField(required=False, allow_null=True)
    core_hours_end = serializers.TimeField(required=False, allow_null=True)
    hours_per_day = serializers.DecimalField(max_digits=4, decimal_places=2, required=False)
    approver = serializers.UUIDField(required=False, allow_null=True)
    clear_core_hours = serializers.BooleanField(required=False, default=False)


class OverlapRequestSerializer(serializers.Serializer):
    member_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    duration_minutes = serializers.IntegerField(min_value=1, max_value=24 * 60, default=30)
