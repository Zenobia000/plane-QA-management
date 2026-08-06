# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Which halves of which days a person is away.

Occupancy is tracked as a **pair of booleans per date** -- morning taken, afternoon taken --
and combined by union rather than by adding fractions. That is the whole trick: a half-day
of leave on the same Wednesday as an all-hands is one half plus one full day, and summing
them removes 1.5 days from an 8-hour day. A union cannot exceed the day, so the
double-deduction ADR 0008 warns about is not a bug that has to be caught -- it is a
statement the type cannot express.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from plane.db.models import DayPart, EventAudience, LeaveStatus, MemberLeave, TeamEvent

# Statuses that actually remove somebody from work. A pending request has not been decided,
# so planning against it would be planning against a guess.
BINDING_STATUSES = (LeaveStatus.APPROVED,)


@dataclass
class Halves:
    """Which halves of one day are taken."""

    morning: bool = False
    afternoon: bool = False

    def union(self, other: "Halves") -> "Halves":
        return Halves(self.morning or other.morning, self.afternoon or other.afternoon)

    @property
    def fraction(self) -> Decimal:
        return Decimal("0.5") * (int(self.morning) + int(self.afternoon))

    @property
    def whole_day(self) -> bool:
        return self.morning and self.afternoon


def halves_on(day: date, start: date, end: date, start_part: str, end_part: str) -> Halves:
    """Which halves of `day` a range covers.

    The interesting cases are the two ends. `MemberLeave.clean()` guarantees a multi-day
    range never starts in the morning or ends in the afternoon -- those would be full days
    anyway -- so the only partial ends are "starts after lunch" and "ends at lunch".
    """
    if day < start or day > end:
        return Halves()

    if start == end:
        if start_part == DayPart.MORNING:
            return Halves(morning=True)
        if start_part == DayPart.AFTERNOON:
            return Halves(afternoon=True)
        return Halves(True, True)

    if day == start:
        return Halves(morning=start_part != DayPart.AFTERNOON, afternoon=True)
    if day == end:
        return Halves(morning=True, afternoon=end_part != DayPart.MORNING)
    return Halves(True, True)


def _walk(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def member_occupancy(*, workspace, start, end, member_ids=None, capacity_only=True):
    """`{member_id: {date: Halves}}` for a workspace over a range.

    `capacity_only` keeps out the absences that do not remove somebody from work -- a leave
    type marked "working remotely" belongs on the wallchart but not in a capacity
    subtraction. The wallchart passes False.
    """
    occupancy: dict[str, dict[date, Halves]] = {}

    def add(member_id, day, halves):
        if not (halves.morning or halves.afternoon):
            return
        member_id = str(member_id)
        bucket = occupancy.setdefault(member_id, {})
        bucket[day] = bucket.get(day, Halves()).union(halves)

    leaves = MemberLeave.objects.filter(
        workspace=workspace,
        status__in=BINDING_STATUSES,
        start_date__lte=end,
        end_date__gte=start,
    ).select_related("leave_type")
    if member_ids:
        leaves = leaves.filter(member_id__in=member_ids)
    if capacity_only:
        leaves = leaves.filter(leave_type__consumes_capacity=True)

    for leave in leaves:
        for day in _walk(max(leave.start_date, start), min(leave.end_date, end)):
            add(
                leave.member_id,
                day,
                halves_on(day, leave.start_date, leave.end_date, leave.start_day_part, leave.end_day_part),
            )

    events = TeamEvent.objects.filter(
        workspace=workspace, start_date__lte=end, end_date__gte=start
    ).prefetch_related("attendees")
    if capacity_only:
        events = events.filter(consumes_capacity=True)

    roster = [str(value) for value in member_ids] if member_ids else None
    for event in events:
        if event.audience == EventAudience.ALL_MEMBERS:
            # An event for everyone still needs a roster to attribute it to; without one
            # the caller only wants named attendees and gets them below.
            targets = roster if roster is not None else _workspace_member_ids(workspace)
        else:
            targets = [str(attendee.member_id) for attendee in event.attendees.all()]
            if roster is not None:
                targets = [value for value in targets if value in roster]

        for day in _walk(max(event.start_date, start), min(event.end_date, end)):
            slice_ = halves_on(day, event.start_date, event.end_date, event.start_day_part, event.end_day_part)
            for member_id in targets:
                add(member_id, day, slice_)

    return occupancy


def _workspace_member_ids(workspace):
    from plane.db.models import WorkspaceMember

    return [
        str(value)
        for value in WorkspaceMember.objects.filter(workspace=workspace, is_active=True).values_list(
            "member_id", flat=True
        )
    ]
