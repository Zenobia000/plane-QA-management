# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Create regional work calendars for a workspace.

**Only fixed-date public holidays are seeded.** Anything that moves -- Lunar New Year,
Mid-Autumn, Dragon Boat, Japan's Happy Monday holidays, US Thanksgiving -- is left out on
purpose, and so are Taiwan's make-up workdays, because their dates are announced annually
and there is no way to derive them. Shipping a guessed date is worse than shipping none:
a wrong holiday silently changes every leave count that crosses it, and nobody looking at
the number can tell.

The real import path is `set_calendar_days()`, reachable from the API, the CLI and MCP.
Point it at the official published list -- Taiwan's DGPA open data, for instance -- once a
year. This command exists to give a workspace a working starting point, not to be the
source of truth for a national calendar.
"""

from django.core.management.base import BaseCommand, CommandError

from plane.availability import create_work_calendar, set_calendar_days
from plane.db.models import CalendarDayKind, WorkCalendar, Workspace

HOLIDAY = CalendarDayKind.HOLIDAY

# (month, day, name) -- fixed-date only, see the module docstring.
PRESETS = {
    "Taiwan": {
        "timezone": "Asia/Taipei",
        "holidays": [
            (1, 1, "中華民國開國紀念日"),
            (2, 28, "和平紀念日"),
            (4, 4, "兒童節"),
            (5, 1, "勞動節"),
            (10, 10, "國慶日"),
        ],
    },
    "Japan": {
        "timezone": "Asia/Tokyo",
        "holidays": [
            (1, 1, "元日"),
            (2, 11, "建国記念の日"),
            (2, 23, "天皇誕生日"),
            (4, 29, "昭和の日"),
            (5, 3, "憲法記念日"),
            (5, 4, "みどりの日"),
            (5, 5, "こどもの日"),
            (8, 11, "山の日"),
            (11, 3, "文化の日"),
            (11, 23, "勤労感謝の日"),
        ],
    },
    "United States": {
        "timezone": "America/New_York",
        "holidays": [
            (1, 1, "New Year's Day"),
            (6, 19, "Juneteenth"),
            (7, 4, "Independence Day"),
            (11, 11, "Veterans Day"),
            (12, 25, "Christmas Day"),
        ],
    },
}


class Command(BaseCommand):
    help = "Seed regional work calendars with their fixed-date public holidays."

    def add_arguments(self, parser):
        parser.add_argument("--workspace", required=True, help="Workspace slug.")
        parser.add_argument("--year", type=int, required=True, help="Calendar year to populate.")
        parser.add_argument(
            "--region",
            action="append",
            choices=sorted(PRESETS),
            help="Repeatable. Defaults to every preset.",
        )
        parser.add_argument(
            "--default",
            help="Which region becomes the workspace default calendar.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Replace that year's days on a calendar that already exists.",
        )

    def handle(self, *args, **options):
        try:
            workspace = Workspace.objects.get(slug=options["workspace"])
        except Workspace.DoesNotExist as error:
            raise CommandError(f"No workspace with slug '{options['workspace']}'.") from error

        regions = options.get("region") or sorted(PRESETS)
        default_region = options.get("default") or regions[0]
        if default_region not in PRESETS:
            raise CommandError(f"--default must be one of: {', '.join(sorted(PRESETS))}")

        year = options["year"]

        for region in regions:
            preset = PRESETS[region]
            calendar = WorkCalendar.objects.filter(workspace=workspace, name=region).first()

            if calendar is None:
                calendar = create_work_calendar(
                    workspace=workspace,
                    name=region,
                    timezone=preset["timezone"],
                    is_default=region == default_region,
                )
                self.stdout.write(self.style.SUCCESS(f"created calendar {region} ({preset['timezone']})"))
            elif not options["force"]:
                self.stdout.write(f"calendar {region} already exists; pass --force to replace {year}")
                continue

            days = [
                {"date": f"{year}-{month:02d}-{day:02d}", "name": name, "kind": HOLIDAY}
                for month, day, name in preset["holidays"]
            ]
            written = set_calendar_days(calendar=calendar, days=days, replace_year=year)
            self.stdout.write(f"  {len(written)} fixed-date holidays for {year}")

        self.stdout.write(
            self.style.WARNING(
                "Lunar and other moving holidays, and Taiwan's make-up workdays, are NOT seeded — "
                "their dates are announced yearly. Import the official list through the "
                "availability API or CLI, or leave counts crossing them will be wrong."
            )
        )
