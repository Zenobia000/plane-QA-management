# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Vocabularies shared by models that would otherwise each declare their own copy.

This module holds no models and imports nothing from `plane.db`, which is the point:
`portfolio` imports `project`, so a vocabulary the two share cannot live in either without
one of them importing backwards.
"""

from django.db import models


class PortfolioStatus(models.TextChoices):
    """Where a unit of delivery stands.

    Milestone and Initiative each declared a byte-identical copy of this list before Project
    became the third caller. Three copies is three chances for "planned" to drift into
    meaning slightly different things.
    """

    PLANNED = "planned", "Planned"
    IN_PROGRESS = "in_progress", "In progress"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class UpdateStatus(models.TextChoices):
    """The three-way health signal a status update carries.

    Deliberately not the same list as `PortfolioStatus`. "In progress and at risk" is two
    facts, and collapsing them into one column is what forces a team back into writing
    status decks.
    """

    ON_TRACK = "on_track", "On track"
    AT_RISK = "at_risk", "At risk"
    OFF_TRACK = "off_track", "Off track"
