# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The only write path into availability.

Keyword-only, `@transaction.atomic`, and `full_clean()` before every save so the model's
own invariants run rather than being re-implemented per caller. Four trees call this -- the
app API, `/api/v1`, MCP and CLI -- which is the second consumer that makes a service layer
architecture rather than indirection.
"""

from django.db import transaction
from django.utils import timezone

from plane.db.models import (
    CalendarDay,
    DayPart,
    EventAudience,
    LeaveStatus,
    MemberLeave,
    MemberWorkProfile,
    TeamEvent,
    TeamEventAttendee,
    WorkCalendar,
)

# Plane's audit FKs are nullable in the database but not declared as form fields, so a bare
# `full_clean()` rejects every unsaved row for a blank `created_by`. Same exclusion, and same
# reason, as `plane/testing/services.py`.
AUDIT_FIELDS = ("created_by", "updated_by")


def _validate(instance, exclude=()):
    instance.full_clean(exclude=tuple(exclude) + AUDIT_FIELDS)



@transaction.atomic
def create_work_calendar(*, workspace, name, timezone, working_weekdays=None, is_default=False):
    if is_default:
        _clear_default(workspace)
    calendar = WorkCalendar(workspace=workspace, name=name, timezone=timezone, is_default=is_default)
    if working_weekdays is not None:
        calendar.working_weekdays = list(working_weekdays)
    _validate(calendar, ["workspace"])
    calendar.save()
    return calendar


@transaction.atomic
def update_work_calendar(*, calendar, name=None, timezone=None, working_weekdays=None, is_default=None):
    if name is not None:
        calendar.name = name
    if timezone is not None:
        calendar.timezone = timezone
    if working_weekdays is not None:
        calendar.working_weekdays = list(working_weekdays)
    if is_default is not None:
        if is_default:
            _clear_default(calendar.workspace, excluding=calendar.id)
        calendar.is_default = is_default
    _validate(calendar, ["workspace"])
    calendar.save()
    return calendar


def _clear_default(workspace, excluding=None):
    """Only one default may stand, and the constraint is partial-unique rather than a check.

    Demoting the incumbent here instead of asking the caller to means "make this the
    default" cannot half-succeed.
    """
    queryset = WorkCalendar.objects.filter(workspace=workspace, is_default=True)
    if excluding is not None:
        queryset = queryset.exclude(id=excluding)
    queryset.update(is_default=False)


@transaction.atomic
def set_calendar_days(*, calendar, days, replace_year=None):
    """Upsert holidays and make-up workdays for a calendar.

    `replace_year` clears that year first, which is how a published national calendar gets
    re-imported when the government revises it -- the common case, and one that would
    otherwise leave last year's revoked holiday in place.
    """
    if replace_year is not None:
        CalendarDay.objects.filter(calendar=calendar, date__year=replace_year).delete()

    written = []
    for entry in days:
        day, _ = CalendarDay.objects.update_or_create(
            calendar=calendar,
            date=entry["date"],
            defaults={
                "workspace": calendar.workspace,
                "name": entry["name"],
                "kind": entry["kind"],
            },
        )
        written.append(day)
    return written


@transaction.atomic
def upsert_work_profile(
    *,
    workspace,
    member,
    work_calendar=None,
    timezone=None,
    work_start_time=None,
    work_end_time=None,
    core_hours_start=None,
    core_hours_end=None,
    hours_per_day=None,
    approver=None,
    clear_core_hours=False,
):
    """Create or update one member's declared working shape.

    `clear_core_hours` is explicit because `None` already means "leave unchanged" for every
    other field here; without it there would be no way to withdraw a core-hours commitment
    once made.
    """
    profile, _ = MemberWorkProfile.objects.get_or_create(workspace=workspace, member=member)

    if work_calendar is not None:
        profile.work_calendar = work_calendar
    if timezone is not None:
        profile.timezone = timezone or None
    if work_start_time is not None:
        profile.work_start_time = work_start_time
    if work_end_time is not None:
        profile.work_end_time = work_end_time
    if hours_per_day is not None:
        profile.hours_per_day = hours_per_day
    if approver is not None:
        profile.approver = approver

    if clear_core_hours:
        profile.core_hours_start = None
        profile.core_hours_end = None
    else:
        if core_hours_start is not None:
            profile.core_hours_start = core_hours_start
        if core_hours_end is not None:
            profile.core_hours_end = core_hours_end

    _validate(profile, ["workspace", "member"])
    profile.save()
    return profile


@transaction.atomic
def create_leave(
    *,
    workspace,
    member,
    leave_type,
    start_date,
    end_date,
    start_day_part=DayPart.FULL,
    end_day_part=DayPart.FULL,
    reason="",
):
    """Log an absence.

    A type marked `requires_approval=False` lands approved. Routing an absence nobody has
    to decide on through a pending state would produce a queue of requests that exist only
    to be rubber-stamped, and a queue like that stops being read.
    """
    leave = MemberLeave(
        workspace=workspace,
        member=member,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        start_day_part=start_day_part,
        end_day_part=end_day_part,
        reason=reason,
        status=LeaveStatus.PENDING if leave_type.requires_approval else LeaveStatus.APPROVED,
    )
    _validate(leave, ["workspace", "member", "leave_type"])
    leave.save()
    return leave


@transaction.atomic
def cancel_leave(*, leave, actor):
    """Withdraw one's own absence.

    Cancelling is not deleting: the row stays so the wallchart's history remains honest,
    and `member_occupancy` stops counting it because only approved rows bind.
    """
    if leave.status == LeaveStatus.CANCELLED:
        return leave
    leave.status = LeaveStatus.CANCELLED
    leave.decided_by = actor
    leave.decided_at = timezone.now()
    _validate(leave, ["workspace", "member", "leave_type"])
    leave.save()
    return leave


@transaction.atomic
def create_team_event(
    *,
    workspace,
    title,
    start_date,
    end_date,
    project=None,
    description="",
    start_day_part=DayPart.FULL,
    end_day_part=DayPart.FULL,
    colour="#334155",
    consumes_capacity=False,
    audience=EventAudience.ALL_MEMBERS,
    member_ids=(),
):
    event = TeamEvent(
        workspace=workspace,
        project=project,
        title=title,
        description=description,
        start_date=start_date,
        end_date=end_date,
        start_day_part=start_day_part,
        end_day_part=end_day_part,
        colour=colour,
        consumes_capacity=consumes_capacity,
        audience=audience,
    )
    _validate(event, ["workspace", "project"])
    event.save()

    # Attendees are only meaningful for a selected-members event. Storing them for an
    # all-members one would create a second, contradictory answer to "who is this for".
    if audience == EventAudience.SELECTED_MEMBERS:
        for member_id in member_ids:
            attendee = TeamEventAttendee(event=event, workspace=workspace, member_id=member_id)
            _validate(attendee, ["workspace", "event", "member"])
            attendee.save()
    return event
