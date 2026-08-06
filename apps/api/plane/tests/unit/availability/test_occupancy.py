# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""How much of a day an absence takes.

The load-bearing case is the last class: a half-day of leave on the same Wednesday as an
all-hands must remove one day, not one and a half. Summing fractions gets that wrong; a
union of halves cannot get it wrong, which is why occupancy is modelled as two booleans
rather than a number.
"""

from datetime import date, time
from decimal import Decimal

import pytest

from plane.availability import Halves, halves_on, member_occupancy
from plane.availability.schedule import _remaining
from plane.db.models import (
    DayPart,
    EventAudience,
    LeaveStatus,
    LeaveType,
    MemberLeave,
    TeamEvent,
    TeamEventAttendee,
    User,
    WorkspaceMember,
)

MON = date(2026, 8, 3)
TUE = date(2026, 8, 4)
WED = date(2026, 8, 5)


@pytest.mark.unit
class TestHalvesOn:
    def test_a_whole_single_day(self):
        assert halves_on(MON, MON, MON, DayPart.FULL, DayPart.FULL) == Halves(True, True)

    def test_a_single_morning(self):
        assert halves_on(MON, MON, MON, DayPart.MORNING, DayPart.MORNING) == Halves(morning=True)

    def test_a_single_afternoon(self):
        assert halves_on(MON, MON, MON, DayPart.AFTERNOON, DayPart.AFTERNOON) == Halves(afternoon=True)

    def test_a_range_starting_after_lunch(self):
        assert halves_on(MON, MON, WED, DayPart.AFTERNOON, DayPart.FULL) == Halves(afternoon=True)
        assert halves_on(TUE, MON, WED, DayPart.AFTERNOON, DayPart.FULL) == Halves(True, True)

    def test_a_range_ending_at_lunch(self):
        assert halves_on(WED, MON, WED, DayPart.FULL, DayPart.MORNING) == Halves(morning=True)

    def test_days_outside_the_range_are_untouched(self):
        assert halves_on(date(2026, 8, 10), MON, WED, DayPart.FULL, DayPart.FULL) == Halves()

    def test_a_two_and_a_half_day_absence(self):
        """Afternoon of Monday through Wednesday: 0.5 + 1 + 1."""
        total = sum(
            (halves_on(day, MON, WED, DayPart.AFTERNOON, DayPart.FULL).fraction for day in (MON, TUE, WED)),
            Decimal(0),
        )

        assert total == Decimal("2.5")


@pytest.mark.unit
class TestHalvesUnion:
    def test_a_union_cannot_exceed_one_day(self):
        full = Halves(True, True)

        assert full.union(Halves(morning=True)).fraction == Decimal("1.0")

    def test_two_different_halves_make_a_whole(self):
        assert Halves(morning=True).union(Halves(afternoon=True)).whole_day is True

    def test_the_same_half_twice_is_still_half(self):
        assert Halves(morning=True).union(Halves(morning=True)).fraction == Decimal("0.5")


@pytest.mark.unit
class TestRemainingWorkingWindow:
    def test_a_free_day_keeps_its_whole_window(self):
        assert _remaining(Halves(), time(9, 0), time(18, 0)) == (time(9, 0), time(18, 0))

    def test_a_full_absence_leaves_nothing(self):
        assert _remaining(Halves(True, True), time(9, 0), time(18, 0)) is None

    def test_a_morning_off_leaves_the_afternoon(self):
        assert _remaining(Halves(morning=True), time(9, 0), time(18, 0)) == (time(13, 30), time(18, 0))

    def test_an_afternoon_off_leaves_the_morning(self):
        assert _remaining(Halves(afternoon=True), time(9, 0), time(18, 0)) == (time(9, 0), time(13, 30))

    def test_the_split_follows_the_declared_day_rather_than_noon(self):
        # Somebody working 08:00-16:00 splits at 12:00, not at whatever the office next
        # door calls lunch.
        assert _remaining(Halves(morning=True), time(8, 0), time(16, 0)) == (time(12, 0), time(16, 0))


@pytest.mark.unit
@pytest.mark.django_db
class TestMemberOccupancy:
    @pytest.fixture
    def annual(self, workspace):
        return LeaveType.objects.create(workspace=workspace, name="Annual", consumes_capacity=True)

    @pytest.fixture
    def remote(self, workspace):
        return LeaveType.objects.create(workspace=workspace, name="Remote", consumes_capacity=False)

    def test_an_approved_leave_occupies_its_days(self, workspace, create_user, annual):
        MemberLeave.objects.create(
            workspace=workspace,
            member=create_user,
            leave_type=annual,
            start_date=MON,
            end_date=TUE,
            status=LeaveStatus.APPROVED,
        )

        occupancy = member_occupancy(workspace=workspace, start=MON, end=WED)

        assert occupancy[str(create_user.id)][MON].whole_day is True
        assert WED not in occupancy[str(create_user.id)]

    def test_a_pending_leave_does_not_bind(self, workspace, create_user, annual):
        """A request nobody has decided on is a guess, and planning against a guess is worse
        than planning against nothing."""
        MemberLeave.objects.create(
            workspace=workspace,
            member=create_user,
            leave_type=annual,
            start_date=MON,
            end_date=MON,
            status=LeaveStatus.PENDING,
        )

        assert member_occupancy(workspace=workspace, start=MON, end=WED) == {}

    def test_a_cancelled_leave_does_not_bind(self, workspace, create_user, annual):
        MemberLeave.objects.create(
            workspace=workspace,
            member=create_user,
            leave_type=annual,
            start_date=MON,
            end_date=MON,
            status=LeaveStatus.CANCELLED,
        )

        assert member_occupancy(workspace=workspace, start=MON, end=WED) == {}

    def test_a_type_that_does_not_consume_capacity_is_excluded_from_capacity(
        self, workspace, create_user, remote
    ):
        MemberLeave.objects.create(
            workspace=workspace,
            member=create_user,
            leave_type=remote,
            start_date=MON,
            end_date=MON,
            status=LeaveStatus.APPROVED,
        )

        assert member_occupancy(workspace=workspace, start=MON, end=WED, capacity_only=True) == {}
        # …but the wallchart still wants to draw it.
        assert member_occupancy(workspace=workspace, start=MON, end=WED, capacity_only=False)

    def test_an_all_members_event_reaches_everyone_active(self, workspace, create_user):
        WorkspaceMember.objects.get_or_create(
            workspace=workspace, member=create_user, defaults={"role": 20, "is_active": True}
        )
        TeamEvent.objects.create(
            workspace=workspace,
            title="All hands",
            start_date=WED,
            end_date=WED,
            consumes_capacity=True,
            audience=EventAudience.ALL_MEMBERS,
        )

        occupancy = member_occupancy(workspace=workspace, start=MON, end=WED)

        assert occupancy[str(create_user.id)][WED].whole_day is True

    def test_a_selected_members_event_reaches_only_its_attendees(self, workspace, create_user):
        outsider = User.objects.create(email="occ-out@plane.so", username="occ-out")
        WorkspaceMember.objects.create(workspace=workspace, member=outsider, role=15, is_active=True)
        event = TeamEvent.objects.create(
            workspace=workspace,
            title="Training",
            start_date=WED,
            end_date=WED,
            consumes_capacity=True,
            audience=EventAudience.SELECTED_MEMBERS,
        )
        TeamEventAttendee.objects.create(event=event, workspace=workspace, member=create_user)

        occupancy = member_occupancy(workspace=workspace, start=MON, end=WED)

        assert str(create_user.id) in occupancy
        assert str(outsider.id) not in occupancy

    def test_a_half_day_of_leave_and_a_full_day_event_remove_exactly_one_day(
        self, workspace, create_user, annual
    ):
        """The reason occupancy is a union of halves rather than a sum of fractions.

        Adding them gives 1.5 days out of an 8-hour Wednesday, which is not a thing that
        can happen.
        """
        WorkspaceMember.objects.get_or_create(
            workspace=workspace, member=create_user, defaults={"role": 20, "is_active": True}
        )
        MemberLeave.objects.create(
            workspace=workspace,
            member=create_user,
            leave_type=annual,
            start_date=WED,
            end_date=WED,
            start_day_part=DayPart.MORNING,
            end_day_part=DayPart.MORNING,
            status=LeaveStatus.APPROVED,
        )
        TeamEvent.objects.create(
            workspace=workspace,
            title="All hands",
            start_date=WED,
            end_date=WED,
            consumes_capacity=True,
            audience=EventAudience.ALL_MEMBERS,
        )

        occupancy = member_occupancy(workspace=workspace, start=WED, end=WED)

        assert occupancy[str(create_user.id)][WED].fraction == Decimal("1.0")

    def test_two_half_days_on_the_same_date_make_one_day_not_two(self, workspace, create_user, annual):
        for part in (DayPart.MORNING, DayPart.AFTERNOON):
            MemberLeave.objects.create(
                workspace=workspace,
                member=create_user,
                leave_type=annual,
                start_date=WED,
                end_date=WED,
                start_day_part=part,
                end_day_part=part,
                status=LeaveStatus.APPROVED,
            )

        occupancy = member_occupancy(workspace=workspace, start=WED, end=WED)

        assert occupancy[str(create_user.id)][WED].fraction == Decimal("1.0")
