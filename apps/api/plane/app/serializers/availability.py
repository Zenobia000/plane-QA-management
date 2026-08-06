# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Read and write shapes for the team calendar.

Read/write split as elsewhere in this fork. Nothing here exposes an observed-activity
field; ADR 0008 bars this surface from `last_active` and a serializer is where such a field
would slip in, since a `fields = "__all__"` on a user relation is all it would take.
"""

from rest_framework import serializers

from plane.db.models import (
    CalendarDay,
    DayPart,
    EventAudience,
    LeaveType,
    MemberLeave,
    MemberWorkProfile,
    TeamEvent,
    WorkCalendar,
)

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


class LeaveTypeSerializer(BaseSerializer):
    class Meta:
        model = LeaveType
        fields = ["id", "name", "colour", "consumes_capacity", "requires_approval", "is_active", "sort_order"]
        read_only_fields = ["id"]


class LeaveTypeWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    colour = serializers.CharField(max_length=7, required=False)
    consumes_capacity = serializers.BooleanField(required=False, default=True)
    requires_approval = serializers.BooleanField(required=False, default=True)
    is_active = serializers.BooleanField(required=False, default=True)
    sort_order = serializers.FloatField(required=False)


class MemberLeaveSerializer(BaseSerializer):
    """A leave, with `reason` shown only to those entitled to it.

    ADR 0008 treats an absence reason as sensitive -- it is medical often enough that
    workspace-wide readability is not a defensible default. The rule lives here rather than
    in a component because a field the API returns is public no matter which client decides
    not to draw it.

    `visible_reason_for` is a set of member ids passed in by the view; empty means nobody.
    """

    class Meta:
        model = MemberLeave
        fields = [
            "id",
            "member",
            "leave_type",
            "start_date",
            "end_date",
            "start_day_part",
            "end_day_part",
            "status",
            "reason",
            "decision_note",
            "decided_by",
            "decided_at",
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.context.get("may_read_reason", lambda _: False)(instance):
            data.pop("reason", None)
            data.pop("decision_note", None)
        return data


class MemberLeaveWriteSerializer(serializers.Serializer):
    leave_type = serializers.UUIDField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    start_day_part = serializers.ChoiceField(choices=DayPart.choices, required=False, default=DayPart.FULL)
    end_day_part = serializers.ChoiceField(choices=DayPart.choices, required=False, default=DayPart.FULL)
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    member = serializers.UUIDField(required=False, help_text="Admins only; defaults to the caller.")


class TeamEventSerializer(BaseSerializer):
    attendee_ids = serializers.SerializerMethodField()

    class Meta:
        model = TeamEvent
        fields = [
            "id",
            "project",
            "title",
            "description",
            "start_date",
            "end_date",
            "start_day_part",
            "end_day_part",
            "colour",
            "consumes_capacity",
            "audience",
            "attendee_ids",
        ]
        read_only_fields = ["id", "attendee_ids"]

    def get_attendee_ids(self, instance):
        return [str(attendee.member_id) for attendee in instance.attendees.all()]


class TeamEventWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    project = serializers.UUIDField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    start_day_part = serializers.ChoiceField(choices=DayPart.choices, required=False, default=DayPart.FULL)
    end_day_part = serializers.ChoiceField(choices=DayPart.choices, required=False, default=DayPart.FULL)
    colour = serializers.CharField(max_length=7, required=False, default="#334155")
    consumes_capacity = serializers.BooleanField(required=False, default=False)
    audience = serializers.ChoiceField(choices=EventAudience.choices, required=False, default=EventAudience.ALL_MEMBERS)
    member_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
