# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""When each member of a workspace is reachable, and on which days.

Workspace-scoped rather than project-scoped, which is the first time this fork departs
from "Project is the aggregate boundary". The argument is in ADR 0008: a person's working
hours and absences are one fact about that person, and storing them per project would keep
N copies that can disagree.

Two rules here are prohibitions rather than features, and both come from the same place --
this is a coordination tool, not a monitoring one:

* Nothing in this module may read or expose `User.last_active`. Availability is what
  someone *declares*, never what they were observed doing.
* Granularity stops at the half-day for absence and at the working window for presence.
  Anything finer turns a calendar into a timesheet.
"""

from datetime import time

import pytz
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.postgres.fields import ArrayField
from django.db import models

from .base import BaseModel

TIMEZONE_CHOICES = tuple(zip(pytz.common_timezones, pytz.common_timezones))

# ISO-8601 weekday numbers, so Monday is 1 and Sunday is 7. Python's `date.isoweekday()`
# returns the same, which keeps `working_days()` free of an off-by-one conversion.
DEFAULT_WORKING_WEEKDAYS = [1, 2, 3, 4, 5]

DEFAULT_WORK_START = time(9, 0)
DEFAULT_WORK_END = time(18, 0)


def default_working_weekdays():
    """A callable, because a mutable default would be shared by every row."""
    return list(DEFAULT_WORKING_WEEKDAYS)


class WorkCalendar(BaseModel):
    """Which days a region works, and what its clock reads.

    One workspace can hold several: a team split across Taipei and Berlin does not share a
    holiday list, and pretending otherwise silently miscounts every leave request that
    crosses one.
    """

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="work_calendars")
    name = models.CharField(max_length=255)
    timezone = models.CharField(max_length=255, choices=TIMEZONE_CHOICES, default="UTC")
    working_weekdays = ArrayField(
        models.PositiveSmallIntegerField(),
        default=default_working_weekdays,
        help_text="ISO weekday numbers, Monday=1 … Sunday=7.",
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Used by members who have not been assigned one.",
    )

    class Meta:
        verbose_name = "Work Calendar"
        verbose_name_plural = "Work Calendars"
        db_table = "work_calendars"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_work_calendar_name",
            ),
            models.UniqueConstraint(
                fields=["workspace"],
                condition=models.Q(is_default=True, deleted_at__isnull=True),
                name="unique_default_work_calendar_per_workspace",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.timezone})"

    def clean(self):
        if not self.working_weekdays:
            raise ValidationError("A work calendar must have at least one working weekday.")
        if any(day < 1 or day > 7 for day in self.working_weekdays):
            raise ValidationError("Working weekdays are ISO numbers between 1 (Monday) and 7 (Sunday).")
        if len(set(self.working_weekdays)) != len(self.working_weekdays):
            raise ValidationError("Working weekdays cannot repeat.")


class CalendarDayKind(models.TextChoices):
    HOLIDAY = "holiday", "Holiday"
    MAKEUP_WORKDAY = "makeup_workday", "Make-up workday"


class CalendarDay(BaseModel):
    """A single date that overrides its calendar's weekday rule.

    `MAKEUP_WORKDAY` exists because Taiwan has them: a Saturday the whole country works to
    bridge a long weekend. A model carrying only a weekday mask and a holiday list cannot
    express that day at all, and every leave request spanning one comes out short.
    """

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="calendar_days")
    calendar = models.ForeignKey(WorkCalendar, on_delete=models.CASCADE, related_name="days")
    date = models.DateField()
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=32, choices=CalendarDayKind.choices, default=CalendarDayKind.HOLIDAY)

    class Meta:
        verbose_name = "Calendar Day"
        verbose_name_plural = "Calendar Days"
        db_table = "calendar_days"
        ordering = ("date",)
        constraints = [
            models.UniqueConstraint(
                fields=["calendar", "date"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_calendar_day",
            )
        ]
        indexes = [models.Index(fields=["calendar", "date"], name="calendar_day_lookup_idx")]

    def __str__(self):
        return f"{self.date} {self.name}"

    def clean(self):
        if self.calendar_id and self.calendar.workspace_id != self.workspace_id:
            raise ValidationError("A calendar day must belong to the same workspace as its calendar.")


class MemberWorkProfile(BaseModel):
    """One member's declared working shape.

    The working window is stored as naive times and read in the member's resolved zone,
    which is what lets two people in different cities be drawn on one axis.

    `core_hours_*` is narrower than the working window and optional. "I work 09:00-18:00"
    and "you can interrupt me any time in that span" are different claims, and a remote
    team that treats them as one ends up with a calendar nobody trusts.
    """

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="member_work_profiles")
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="work_profiles")
    work_calendar = models.ForeignKey(
        WorkCalendar,
        on_delete=models.SET_NULL,
        related_name="member_profiles",
        null=True,
        blank=True,
        help_text="Falls back to the workspace default when unset.",
    )
    timezone = models.CharField(
        max_length=255,
        choices=TIMEZONE_CHOICES,
        null=True,
        blank=True,
        help_text="Overrides the calendar's zone. Falls back to the calendar, then User.user_timezone.",
    )
    # `time` objects rather than "09:00" strings: a string default is only converted on
    # save, so an unsaved instance would hand a str to datetime.combine().
    work_start_time = models.TimeField(default=DEFAULT_WORK_START)
    work_end_time = models.TimeField(default=DEFAULT_WORK_END)
    core_hours_start = models.TimeField(null=True, blank=True)
    core_hours_end = models.TimeField(null=True, blank=True)
    hours_per_day = models.DecimalField(max_digits=4, decimal_places=2, default=8)
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="availability_approvals",
        null=True,
        blank=True,
        help_text="Decides this member's leave. Unset means any workspace admin may.",
    )

    class Meta:
        verbose_name = "Member Work Profile"
        verbose_name_plural = "Member Work Profiles"
        db_table = "member_work_profiles"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "member"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_member_work_profile",
            )
        ]

    def __str__(self):
        return f"{self.member_id} {self.work_start_time}-{self.work_end_time}"

    def clean(self):
        if self.work_calendar_id and self.work_calendar.workspace_id != self.workspace_id:
            raise ValidationError("A work calendar must belong to the same workspace as the profile.")
        if self.work_start_time >= self.work_end_time:
            raise ValidationError("A working day must start before it ends.")
        if self.hours_per_day <= 0 or self.hours_per_day > 24:
            raise ValidationError("Hours per day must be greater than zero and no more than 24.")
        # Both or neither: one half of a core window is not a claim anyone can act on.
        if bool(self.core_hours_start) != bool(self.core_hours_end):
            raise ValidationError("Core hours need both a start and an end.")
        if self.core_hours_start and self.core_hours_end:
            if self.core_hours_start >= self.core_hours_end:
                raise ValidationError("Core hours must start before they end.")
            if self.core_hours_start < self.work_start_time or self.core_hours_end > self.work_end_time:
                raise ValidationError("Core hours must fall inside the working window.")


class DayPart(models.TextChoices):
    """Which half of a day an absence covers.

    The granularity stops here on purpose. Half a day keeps the arithmetic exact and the
    calendar drawable; "out 14:00-15:30" would turn a coordination tool into a timesheet,
    which ADR 0008 rules out.
    """

    FULL = "full", "Full day"
    MORNING = "morning", "Morning"
    AFTERNOON = "afternoon", "Afternoon"


class LeaveStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"


class LeaveType(BaseModel):
    """A kind of absence, as workspace data rather than a choice enum.

    Names are user data. Compiling "annual leave" and "sick leave" into the product would
    make every workspace inherit one organisation's vocabulary, and the fork already keeps
    category names out of code (codebase-map invariant 9).
    """

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="leave_types")
    name = models.CharField(max_length=255)
    colour = models.CharField(max_length=7, default="#6B7280", help_text="Hex, for the wallchart.")
    consumes_capacity = models.BooleanField(
        default=True,
        help_text="False for absences that do not remove the person from work, e.g. working remotely.",
    )
    requires_approval = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.FloatField(default=65535)

    class Meta:
        verbose_name = "Leave Type"
        verbose_name_plural = "Leave Types"
        db_table = "leave_types"
        ordering = ("sort_order", "name")
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_leave_type_name",
            )
        ]

    def __str__(self):
        return self.name


class MemberLeave(BaseModel):
    """One person, away, for a stretch of days.

    `reason` is treated as sensitive: the serializer shows it only to the member, their
    resolved approver, and workspace admins. Everyone else sees the type and the dates.
    """

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="member_leaves")
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="leaves")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name="leaves")
    start_date = models.DateField()
    end_date = models.DateField()
    start_day_part = models.CharField(max_length=16, choices=DayPart.choices, default=DayPart.FULL)
    end_day_part = models.CharField(max_length=16, choices=DayPart.choices, default=DayPart.FULL)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=LeaveStatus.choices, default=LeaveStatus.PENDING)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="leave_decisions",
        null=True,
        blank=True,
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)

    class Meta:
        verbose_name = "Member Leave"
        verbose_name_plural = "Member Leaves"
        db_table = "member_leaves"
        ordering = ("-start_date",)
        indexes = [
            models.Index(fields=["workspace", "start_date", "end_date"], name="leave_range_idx"),
            models.Index(fields=["member", "start_date"], name="leave_member_idx"),
        ]

    def __str__(self):
        return f"{self.member_id} {self.start_date}..{self.end_date}"

    def clean(self):
        if self.leave_type_id and self.leave_type.workspace_id != self.workspace_id:
            raise ValidationError("A leave type must belong to the same workspace as the leave.")
        if self.start_date > self.end_date:
            raise ValidationError("Leave cannot end before it starts.")

        if self.start_date == self.end_date:
            # One day, one claim. Two different halves of the same day is not a thing
            # anyone can mean, and letting it through would double-count the day.
            if self.start_day_part != self.end_day_part:
                raise ValidationError("A single-day leave must use the same day part at both ends.")
        else:
            if self.start_day_part == DayPart.MORNING:
                raise ValidationError("A multi-day leave starting in the morning is a full first day.")
            if self.end_day_part == DayPart.AFTERNOON:
                raise ValidationError("A multi-day leave ending in the afternoon is a full last day.")


class EventAudience(models.TextChoices):
    ALL_MEMBERS = "all_members", "All members"
    SELECTED_MEMBERS = "selected_members", "Selected members"


class TeamEvent(BaseModel):
    """Something that takes the team, or part of it, away from project work.

    Separate from `MemberLeave` because the two differ in owner, lifecycle and cardinality.
    One table for both would leave half its columns null for half its rows, and `status =
    approved` would be meaningless on the half that is never approved.
    """

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="team_events")
    project = models.ForeignKey(
        "db.Project",
        on_delete=models.CASCADE,
        related_name="team_events",
        null=True,
        blank=True,
        help_text="Narrows what the event is about. Never narrows where an absence lives.",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    start_day_part = models.CharField(max_length=16, choices=DayPart.choices, default=DayPart.FULL)
    end_day_part = models.CharField(max_length=16, choices=DayPart.choices, default=DayPart.FULL)
    colour = models.CharField(max_length=7, default="#334155")
    consumes_capacity = models.BooleanField(
        default=False,
        help_text="True for training or an offsite; false for a release date nobody attends.",
    )
    audience = models.CharField(
        max_length=32,
        choices=EventAudience.choices,
        default=EventAudience.ALL_MEMBERS,
        help_text="Declared, not inferred from whether attendees happen to be listed.",
    )

    class Meta:
        verbose_name = "Team Event"
        verbose_name_plural = "Team Events"
        db_table = "team_events"
        ordering = ("-start_date",)
        indexes = [models.Index(fields=["workspace", "start_date", "end_date"], name="team_event_range_idx")]

    def __str__(self):
        return f"{self.title} {self.start_date}"

    def clean(self):
        if self.project_id and self.project.workspace_id != self.workspace_id:
            raise ValidationError("A team event's project must belong to the same workspace.")
        if self.start_date > self.end_date:
            raise ValidationError("An event cannot end before it starts.")
        if self.start_date == self.end_date and self.start_day_part != self.end_day_part:
            raise ValidationError("A single-day event must use the same day part at both ends.")


class TeamEventAttendee(BaseModel):
    event = models.ForeignKey(TeamEvent, on_delete=models.CASCADE, related_name="attendees")
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="team_event_attendees")
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="team_events")

    class Meta:
        verbose_name = "Team Event Attendee"
        verbose_name_plural = "Team Event Attendees"
        db_table = "team_event_attendees"
        constraints = [
            models.UniqueConstraint(
                fields=["event", "member"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_team_event_attendee",
            )
        ]

    def clean(self):
        if self.event_id and self.event.workspace_id != self.workspace_id:
            raise ValidationError("An attendee must belong to the same workspace as the event.")
