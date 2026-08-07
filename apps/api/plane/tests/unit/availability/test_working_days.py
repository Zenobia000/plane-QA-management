# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Which dates count as working days.

No database: `working_days` is handed its overrides, so these are plain function tests over
an unsaved calendar. The date arithmetic is where this feature is either right or quietly
wrong by a day, and a wrong day here becomes a wrong capacity number four slices later.
"""

from datetime import date

import pytest

from plane.availability import working_days
from plane.db.models import CalendarDayKind, WorkCalendar

HOLIDAY = CalendarDayKind.HOLIDAY
MAKEUP = CalendarDayKind.MAKEUP_WORKDAY


def calendar(weekdays=None):
    return WorkCalendar(name="Taiwan", timezone="Asia/Taipei", working_weekdays=weekdays or [1, 2, 3, 4, 5])


@pytest.mark.unit
class TestWorkingDays:
    def test_weekend_is_excluded_by_the_weekday_mask(self):
        # 2026-08-03 is a Monday, 2026-08-09 a Sunday.
        days = working_days(calendar(), date(2026, 8, 3), date(2026, 8, 9), {})

        assert days == [date(2026, 8, i) for i in range(3, 8)]

    def test_a_holiday_is_removed(self):
        days = working_days(
            calendar(),
            date(2026, 8, 3),
            date(2026, 8, 7),
            {date(2026, 8, 5): HOLIDAY},
        )

        assert date(2026, 8, 5) not in days
        assert len(days) == 4

    def test_a_makeup_workday_turns_a_saturday_into_a_working_day(self):
        """The case a weekday-mask-plus-holiday-list model cannot express at all.

        Taiwan bridges long weekends by working a Saturday. Without this, every leave
        request spanning one comes out a day short and nobody can see why.
        """
        days = working_days(
            calendar(),
            date(2026, 8, 3),
            date(2026, 8, 9),
            {date(2026, 8, 8): MAKEUP},
        )

        assert date(2026, 8, 8) in days
        assert len(days) == 6

    def test_a_makeup_workday_on_an_ordinary_weekday_is_not_counted_twice(self):
        days = working_days(
            calendar(),
            date(2026, 8, 3),
            date(2026, 8, 7),
            {date(2026, 8, 5): MAKEUP},
        )

        assert days.count(date(2026, 8, 5)) == 1
        assert len(days) == 5

    def test_a_holiday_falling_on_a_weekend_changes_nothing(self):
        days = working_days(
            calendar(),
            date(2026, 8, 3),
            date(2026, 8, 9),
            {date(2026, 8, 9): HOLIDAY},
        )

        assert len(days) == 5

    def test_a_range_crossing_a_month_boundary(self):
        # 2026-08-31 is a Monday; September opens Tue-Fri.
        days = working_days(calendar(), date(2026, 8, 31), date(2026, 9, 4), {})

        assert days[0] == date(2026, 8, 31)
        assert days[-1] == date(2026, 9, 4)
        assert len(days) == 5

    def test_a_range_crossing_a_year_boundary(self):
        # 2026-12-28 Mon .. 2027-01-01 Fri, with New Year's Day off.
        days = working_days(
            calendar(),
            date(2026, 12, 28),
            date(2027, 1, 1),
            {date(2027, 1, 1): HOLIDAY},
        )

        assert days == [date(2026, 12, i) for i in range(28, 32)]

    def test_a_single_working_day(self):
        assert working_days(calendar(), date(2026, 8, 5), date(2026, 8, 5), {}) == [date(2026, 8, 5)]

    def test_a_single_non_working_day(self):
        assert working_days(calendar(), date(2026, 8, 8), date(2026, 8, 8), {}) == []

    def test_an_inverted_range_yields_nothing_rather_than_looping(self):
        assert working_days(calendar(), date(2026, 8, 9), date(2026, 8, 3), {}) == []

    def test_a_six_day_week_is_expressible(self):
        """Some teams work Saturdays as a rule, not as a make-up day."""
        days = working_days(calendar([1, 2, 3, 4, 5, 6]), date(2026, 8, 3), date(2026, 8, 9), {})

        assert len(days) == 6
        assert date(2026, 8, 9) not in days

    def test_a_workspace_with_no_calendar_falls_back_to_monday_to_friday(self):
        """Wrong for somebody, but visibly and editably wrong.

        Returning nothing instead would make the whole surface look broken before anyone
        had a chance to configure it.
        """
        days = working_days(None, date(2026, 8, 3), date(2026, 8, 9), {})

        assert len(days) == 5

    def test_holidays_outside_the_range_are_ignored(self):
        days = working_days(
            calendar(),
            date(2026, 8, 3),
            date(2026, 8, 7),
            {date(2026, 9, 1): HOLIDAY},
        )

        assert len(days) == 5
