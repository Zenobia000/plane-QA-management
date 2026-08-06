# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Which days count as working days, and whose clock we read them on.

Framework-agnostic: takes model instances, returns plain values, touches no request and no
serializer. Four callers need this answer -- the app tree, `/api/v1`, the MCP server and
the CLI -- which is why it is a service layer rather than logic in a view.
"""

from datetime import date, timedelta

from plane.db.models import CalendarDayKind, WorkCalendar

# Used when a workspace has not defined a calendar at all. Monday to Friday with no
# holidays is wrong for somebody, but it is wrong in a way that is visible and editable,
# whereas returning nothing would make the whole surface look broken.
FALLBACK_WORKING_WEEKDAYS = frozenset({1, 2, 3, 4, 5})
FALLBACK_TIMEZONE = "UTC"


def default_calendar(workspace_id):
    """The calendar members inherit when they have not been assigned one."""
    return WorkCalendar.objects.filter(workspace_id=workspace_id, is_default=True).first()


def resolve_calendar(profile, workspace_id, default=None):
    """A member's calendar, falling back to the workspace default.

    `default` lets a caller resolving many members hand in one already-fetched row rather
    than querying per member.
    """
    if profile is not None and profile.work_calendar_id:
        return profile.work_calendar
    return default if default is not None else default_calendar(workspace_id)


def resolve_timezone(profile, calendar, user=None):
    """Profile override, then the calendar's region, then whatever Plane already knows.

    `User.user_timezone` is the last step deliberately: it exists and is maintained, so
    asking somebody to state where they are a second time would be the wrong kind of
    thorough.
    """
    if profile is not None and profile.timezone:
        return profile.timezone
    if calendar is not None and calendar.timezone:
        return calendar.timezone
    return getattr(user, "user_timezone", None) or FALLBACK_TIMEZONE


def calendar_overrides(calendar, start, end):
    """`{date: kind}` for the dates in range that override their weekday rule."""
    if calendar is None:
        return {}
    return {day.date: day.kind for day in calendar.days.filter(date__gte=start, date__lte=end)}


def working_days(calendar, start, end, overrides=None):
    """Every working date in `[start, end]`, inclusive.

    A make-up workday counts however the weekday mask reads -- that is the whole point of
    the row. Taiwan bridges long weekends by working a Saturday, and a model that only
    knows "weekends are off, plus this holiday list" cannot represent that day, so every
    span containing one comes out a day short.
    """
    if start > end:
        return []
    if overrides is None:
        overrides = calendar_overrides(calendar, start, end)

    mask = set(calendar.working_weekdays) if calendar is not None else set(FALLBACK_WORKING_WEEKDAYS)

    days = []
    current = start
    while current <= end:
        kind = overrides.get(current)
        if kind == CalendarDayKind.MAKEUP_WORKDAY:
            days.append(current)
        elif kind != CalendarDayKind.HOLIDAY and current.isoweekday() in mask:
            days.append(current)
        current += timedelta(days=1)
    return days


def is_working_day(calendar, day: date, overrides=None) -> bool:
    return bool(working_days(calendar, day, day, overrides))
