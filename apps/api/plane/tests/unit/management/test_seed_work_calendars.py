# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Seeding regional calendars.

The idempotency case matters because this command will be run once a year, by hand, by
someone who does not remember whether they already ran it.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from plane.db.models import CalendarDay, CalendarDayKind, WorkCalendar


def seed(workspace, **kwargs):
    out = StringIO()
    call_command("seed_work_calendars", workspace=workspace.slug, year=2026, stdout=out, **kwargs)
    return out.getvalue()


@pytest.mark.unit
@pytest.mark.django_db
class TestSeedWorkCalendars:
    def test_it_creates_every_preset_with_one_default(self, workspace):
        seed(workspace)

        calendars = WorkCalendar.objects.filter(workspace=workspace)
        assert calendars.count() == 3
        assert calendars.filter(is_default=True).count() == 1

    def test_a_region_can_be_chosen(self, workspace):
        seed(workspace, region=["Taiwan"])

        assert [c.name for c in WorkCalendar.objects.filter(workspace=workspace)] == ["Taiwan"]

    def test_taiwan_gets_its_fixed_date_holidays(self, workspace):
        seed(workspace, region=["Taiwan"])

        days = CalendarDay.objects.filter(workspace=workspace)
        assert days.count() == 5
        assert days.filter(date="2026-02-28").exists()
        assert all(day.kind == CalendarDayKind.HOLIDAY for day in days)

    def test_running_twice_neither_duplicates_nor_errors(self, workspace):
        seed(workspace, region=["Taiwan"])
        output = seed(workspace, region=["Taiwan"])

        assert WorkCalendar.objects.filter(workspace=workspace).count() == 1
        assert CalendarDay.objects.filter(workspace=workspace).count() == 5
        assert "already exists" in output

    def test_force_replaces_the_year_without_duplicating(self, workspace):
        seed(workspace, region=["Taiwan"])
        CalendarDay.objects.filter(workspace=workspace, date="2026-02-28").delete()

        seed(workspace, region=["Taiwan"], force=True)

        assert CalendarDay.objects.filter(workspace=workspace).count() == 5

    def test_it_says_out_loud_what_it_did_not_seed(self, workspace):
        """A silent omission here becomes a wrong day count nobody can explain.

        Lunar holidays and Taiwan's make-up workdays are announced yearly, so this command
        cannot know them -- and shipping a guessed date would be worse than shipping none.
        """
        output = seed(workspace, region=["Taiwan"])

        assert "make-up workdays" in output
        assert "NOT seeded" in output

    def test_an_unknown_workspace_fails_loudly(self, db):
        class Missing:
            slug = "no-such-workspace"

        with pytest.raises(CommandError):
            seed(Missing())
