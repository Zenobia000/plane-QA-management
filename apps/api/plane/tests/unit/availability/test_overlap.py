# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""When two people in different cities are reachable at the same moment.

No database: `member_schedule` is handed its calendar and its override cache, so these run
as plain function tests. Every assertion is an instant in UTC, because "Tuesday 09:00" is
not a comparable quantity until it has a zone attached -- and the bug this module exists to
avoid is exactly the one where it looks like it is.
"""

from datetime import date, datetime, time

import pytest
import pytz

from plane.availability import Window, common_windows, intersect, member_schedule
from plane.db.models import MemberWorkProfile, WorkCalendar

MONDAY = date(2026, 8, 3)
FRIDAY = date(2026, 8, 7)


def utc(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=pytz.UTC)


def calendar(timezone):
    return WorkCalendar(name=timezone, timezone=timezone, working_weekdays=[1, 2, 3, 4, 5])


def schedule_for(timezone, *, start=time(9, 0), end=time(18, 0), core=None, day_from=MONDAY, day_to=MONDAY):
    cal = calendar(timezone)
    profile = MemberWorkProfile(
        work_calendar=cal,
        work_start_time=start,
        work_end_time=end,
        core_hours_start=core[0] if core else None,
        core_hours_end=core[1] if core else None,
    )
    return member_schedule(
        profile=profile,
        user=None,
        workspace_id=None,
        start=day_from,
        end=day_to,
        default_cal=cal,
        overrides_cache={cal.id: {}},
    )


@pytest.mark.unit
class TestIntersect:
    def test_two_identical_windows(self):
        window = Window(utc(2026, 8, 3, 9), utc(2026, 8, 3, 18))

        assert intersect([window], [window]) == [window]

    def test_partial_overlap_keeps_only_the_shared_part(self):
        left = Window(utc(2026, 8, 3, 9), utc(2026, 8, 3, 18))
        right = Window(utc(2026, 8, 3, 15), utc(2026, 8, 3, 23))

        assert intersect([left], [right]) == [Window(utc(2026, 8, 3, 15), utc(2026, 8, 3, 18))]

    def test_windows_that_merely_touch_do_not_overlap(self):
        """Ending exactly when the other begins is not a moment anyone can meet in."""
        left = Window(utc(2026, 8, 3, 9), utc(2026, 8, 3, 12))
        right = Window(utc(2026, 8, 3, 12), utc(2026, 8, 3, 18))

        assert intersect([left], [right]) == []

    def test_disjoint_windows(self):
        left = Window(utc(2026, 8, 3, 9), utc(2026, 8, 3, 10))
        right = Window(utc(2026, 8, 3, 14), utc(2026, 8, 3, 15))

        assert intersect([left], [right]) == []

    def test_one_window_spanning_several(self):
        wide = Window(utc(2026, 8, 3, 0), utc(2026, 8, 3, 23))
        narrow = [
            Window(utc(2026, 8, 3, 9), utc(2026, 8, 3, 10)),
            Window(utc(2026, 8, 3, 14), utc(2026, 8, 3, 15)),
        ]

        assert intersect([wide], narrow) == narrow

    def test_either_side_empty(self):
        assert intersect([], [Window(utc(2026, 8, 3, 9), utc(2026, 8, 3, 18))]) == []
        assert intersect([Window(utc(2026, 8, 3, 9), utc(2026, 8, 3, 18))], []) == []


@pytest.mark.unit
class TestMemberSchedule:
    def test_local_hours_become_absolute_instants(self):
        taipei = schedule_for("Asia/Taipei")

        # 09:00 in UTC+8 is 01:00 UTC.
        assert taipei.working == [Window(utc(2026, 8, 3, 1), utc(2026, 8, 3, 10))]
        assert taipei.timezone == "Asia/Taipei"

    def test_a_non_working_day_produces_no_window(self):
        saturday = date(2026, 8, 8)
        taipei = schedule_for("Asia/Taipei", day_from=saturday, day_to=saturday)

        assert taipei.working == []

    def test_a_member_with_no_profile_declares_nothing(self):
        """Empty, not an invented 09:00-18:00.

        Guessing would put a claim on screen that the person never made, and colleagues
        would then plan around it.
        """
        cal = calendar("Asia/Taipei")
        result = member_schedule(
            profile=None,
            user=type("U", (), {"id": "u1", "user_timezone": "Asia/Taipei"})(),
            workspace_id=None,
            start=MONDAY,
            end=FRIDAY,
            default_cal=cal,
            overrides_cache={cal.id: {}},
        )

        assert result.working == []
        assert result.timezone == "Asia/Taipei"

    def test_daylight_saving_moves_the_absolute_window(self):
        """Berlin is UTC+2 in August and UTC+1 in January, for the same local 09:00.

        A fixed offset would put this window an hour out for half the year, and the error
        would only ever show up as a meeting nobody could attend.
        """
        summer = schedule_for("Europe/Berlin", day_from=date(2026, 8, 3), day_to=date(2026, 8, 3))
        winter = schedule_for("Europe/Berlin", day_from=date(2026, 1, 5), day_to=date(2026, 1, 5))

        assert summer.working[0].start == utc(2026, 8, 3, 7)
        assert winter.working[0].start == utc(2026, 1, 5, 8)


@pytest.mark.unit
class TestCommonWindows:
    def test_taipei_and_berlin_share_the_end_of_one_day_and_the_start_of_the_other(self):
        taipei = schedule_for("Asia/Taipei")  # 01:00-10:00 UTC
        berlin = schedule_for("Europe/Berlin")  # 07:00-16:00 UTC

        result = common_windows([taipei, berlin])

        assert result["working"] == [Window(utc(2026, 8, 3, 7), utc(2026, 8, 3, 10))]

    def test_taipei_and_los_angeles_never_coincide_on_ordinary_hours(self):
        taipei = schedule_for("Asia/Taipei")  # Mon 01:00-10:00 UTC
        la = schedule_for("America/Los_Angeles")  # Mon 16:00 - Tue 01:00 UTC

        assert common_windows([taipei, la])["working"] == []

    def test_a_single_member_is_their_own_overlap(self):
        taipei = schedule_for("Asia/Taipei")

        assert common_windows([taipei])["working"] == taipei.working

    def test_no_members_yields_nothing_rather_than_everything(self):
        assert common_windows([]) == {"core": [], "working": []}

    def test_a_window_shorter_than_the_requested_duration_is_dropped(self):
        taipei = schedule_for("Asia/Taipei")
        berlin = schedule_for("Europe/Berlin")

        # The shared stretch is exactly three hours.
        assert common_windows([taipei, berlin], minimum_minutes=180)["working"]
        assert common_windows([taipei, berlin], minimum_minutes=181)["working"] == []

    def test_core_hours_narrow_the_answer_without_replacing_it(self):
        """Two lists, because they answer different questions.

        "When may I interrupt everyone" is not "when is everyone technically at work", and
        merging them promotes the second into the first.
        """
        taipei = schedule_for("Asia/Taipei", core=(time(16, 0), time(18, 0)))  # 08:00-10:00 UTC
        berlin = schedule_for("Europe/Berlin", core=(time(9, 0), time(12, 0)))  # 07:00-10:00 UTC

        result = common_windows([taipei, berlin])

        assert result["working"] == [Window(utc(2026, 8, 3, 7), utc(2026, 8, 3, 10))]
        assert result["core"] == [Window(utc(2026, 8, 3, 8), utc(2026, 8, 3, 10))]

    def test_a_member_without_core_hours_is_not_the_constraint(self):
        """They have not asked to be protected, so they do not shrink everyone else's window."""
        with_core = schedule_for("Europe/Berlin", core=(time(9, 0), time(12, 0)))  # 07:00-10:00 UTC
        without_core = schedule_for("Europe/Berlin")  # 07:00-16:00 UTC

        result = common_windows([with_core, without_core])

        assert result["core"] == [Window(utc(2026, 8, 3, 7), utc(2026, 8, 3, 10))]

    def test_three_members_fold_down_to_the_common_stretch(self):
        taipei = schedule_for("Asia/Taipei")  # 01:00-10:00
        berlin = schedule_for("Europe/Berlin")  # 07:00-16:00
        london = schedule_for("Europe/London")  # 08:00-17:00

        assert common_windows([taipei, berlin, london])["working"] == [
            Window(utc(2026, 8, 3, 8), utc(2026, 8, 3, 10))
        ]

    def test_a_working_week_yields_one_window_per_shared_day(self):
        taipei = schedule_for("Asia/Taipei", day_from=MONDAY, day_to=FRIDAY)
        berlin = schedule_for("Europe/Berlin", day_from=MONDAY, day_to=FRIDAY)

        assert len(common_windows([taipei, berlin])["working"]) == 5
