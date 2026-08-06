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
