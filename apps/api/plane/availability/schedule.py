# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Reachable windows, and when several people's windows coincide.

Everything here works in absolute UTC intervals rather than in local dates, because that is
the only representation in which Taipei's Tuesday morning and Berlin's Monday evening can
be compared at all. Local dates are used once, to decide which days a person works, and
converted immediately.

Nothing in this module reads observed activity. A window is what somebody declared, and a
person who forgets to record a day off will look reachable -- accepted in ADR 0008 as the
cost of not building surveillance.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

import pytz

from plane.db.models import MemberWorkProfile, WorkspaceMember

from .calendars import (
    calendar_overrides,
    default_calendar,
    resolve_calendar,
    resolve_timezone,
    working_days,
)

# Guards the loop that walks a date range. A year of days is already far past what any
# scheduling question needs, and the endpoint rejects wider ranges rather than paging.
MAX_RANGE_DAYS = 366


@dataclass(frozen=True)
class Window:
    """One reachable stretch, in UTC."""

    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


@dataclass
class MemberSchedule:
    member_id: str
    timezone: str
    calendar_id: str | None
    hours_per_day: float
    working: list[Window]
    core: list[Window]


def _localise(tz, day, clock) -> datetime:
    """A local wall-clock time on a local date, as an absolute instant.

    `localize` rather than `replace(tzinfo=...)`: the offset depends on the date, so a fixed
    tzinfo silently shifts every window on the far side of a daylight-saving change.
    """
    return tz.localize(datetime.combine(day, clock)).astimezone(pytz.UTC)


def member_schedule(*, profile, user, workspace_id, start, end, default_cal=None, overrides_cache=None):
    """One member's working and core windows across a date range."""
    calendar = resolve_calendar(profile, workspace_id, default=default_cal)
    tzname = resolve_timezone(profile, calendar, user)
    tz = pytz.timezone(tzname)

    cache_key = calendar.id if calendar is not None else None
    if overrides_cache is None:
        overrides = calendar_overrides(calendar, start, end)
    else:
        if cache_key not in overrides_cache:
            overrides_cache[cache_key] = calendar_overrides(calendar, start, end)
        overrides = overrides_cache[cache_key]

    work_start = profile.work_start_time if profile else None
    work_end = profile.work_end_time if profile else None
    core_start = profile.core_hours_start if profile else None
    core_end = profile.core_hours_end if profile else None

    # Without a profile there is nothing declared, so there is nothing to draw. Returning
    # empty is honest; inventing 09:00-18:00 would put a claim on screen that the person
    # never made and that others would then plan around.
    working: list[Window] = []
    core: list[Window] = []
    if work_start and work_end:
        for day in working_days(calendar, start, end, overrides):
            working.append(Window(_localise(tz, day, work_start), _localise(tz, day, work_end)))
            if core_start and core_end:
                core.append(Window(_localise(tz, day, core_start), _localise(tz, day, core_end)))

    return MemberSchedule(
        member_id=str(profile.member_id) if profile else str(user.id),
        timezone=tzname,
        calendar_id=str(calendar.id) if calendar else None,
        hours_per_day=float(profile.hours_per_day) if profile else 0.0,
        working=working,
        core=core,
    )


def workspace_schedule(*, workspace, start, end, member_ids=None):
    """Every active member's windows, in one pass.

    One query for the roster, one for the profiles and one per distinct calendar, rather
    than a handful per person.
    """
    members = WorkspaceMember.objects.filter(workspace=workspace, is_active=True).select_related("member")
    if member_ids:
        members = members.filter(member_id__in=member_ids)

    profiles = {
        profile.member_id: profile
        for profile in MemberWorkProfile.objects.filter(
            workspace=workspace, member_id__in=[m.member_id for m in members]
        ).select_related("work_calendar")
    }

    default_cal = default_calendar(workspace.id)
    overrides_cache: dict = {}

    return [
        member_schedule(
            profile=profiles.get(membership.member_id),
            user=membership.member,
            workspace_id=workspace.id,
            start=start,
            end=end,
            default_cal=default_cal,
            overrides_cache=overrides_cache,
        )
        for membership in members
    ]


def intersect(left: list[Window], right: list[Window]) -> list[Window]:
    """Overlap of two sorted, non-overlapping window lists."""
    out: list[Window] = []
    i = j = 0
    while i < len(left) and j < len(right):
        low = max(left[i].start, right[j].start)
        high = min(left[i].end, right[j].end)
        if low < high:
            out.append(Window(low, high))
        # Advance whichever ends first; the other may still meet the next one.
        if left[i].end < right[j].end:
            i += 1
        else:
            j += 1
    return out


def common_windows(schedules: list[MemberSchedule], *, minimum_minutes: int = 30, prefer_core: bool = True):
    """When everybody is reachable at once.

    Returns core-hour overlap separately from working-hour overlap instead of merging them.
    They answer different questions -- "when may I interrupt everyone" versus "when is
    everyone technically at work" -- and a single list would quietly promote the second into
    the first, which is how a calendar stops being trusted.

    A member who declares no core window contributes their working window to the core
    calculation: they have not asked to be protected, so they are not the constraint.
    """
    if not schedules:
        return {"core": [], "working": []}

    def fold(pick):
        result = pick(schedules[0])
        for schedule in schedules[1:]:
            if not result:
                break
            result = intersect(result, pick(schedule))
        return [window for window in result if window.minutes >= minimum_minutes]

    working = fold(lambda s: s.working)
    core = fold(lambda s: s.core or s.working) if prefer_core else []
    return {"core": core, "working": working}


def validate_range(start, end):
    """Both ends present, ordered, and not absurdly wide."""
    if start is None or end is None:
        raise ValueError("Both 'from' and 'to' dates are required.")
    if start > end:
        raise ValueError("'from' must not be after 'to'.")
    if (end - start) > timedelta(days=MAX_RANGE_DAYS):
        raise ValueError(f"Range must not exceed {MAX_RANGE_DAYS} days.")
