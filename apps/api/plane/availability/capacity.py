# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""How much of a cycle a project actually has.

    available = Σ_d (1 − occupancy[d]) × hours_per_day × allocation%
                for d in the member's working days inside the cycle

Three things this deliberately does not do, all from ADR 0008:

* It never reports hours *worked*. Capacity is a planning input; a per-person record of
  effort is the artefact this module exists to avoid.
* It does not accumulate across cycles. The number answers "does this fit", once, for one
  cycle.
* It does not compare against committed work unless the project estimates in time. Story
  points and hours are not commensurate, and a ratio built from two units looks authoritative
  while meaning nothing.
"""

from decimal import Decimal

from plane.db.models import (
    Estimate,
    EstimatePoint,
    Issue,
    MemberProjectAllocation,
    MemberWorkProfile,
    ProjectMember,
)

# Not re-exported from `plane.db.models`; imported from its module rather than widening an
# upstream registry for one name.
from plane.db.models.estimate import EstimateType

from .absence import member_occupancy
from .calendars import calendar_overrides, default_calendar, resolve_calendar, working_days

FULL_ALLOCATION = Decimal(100)


def _round(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01")))


def cycle_capacity(*, cycle):
    """Per-member available hours for one project's cycle.

    Returns members with an allocation to this project, or -- when nobody has been allocated
    yet -- every project member at 100%. Showing an empty panel until someone fills in the
    allocation matrix would make the feature look broken on the day it ships.
    """
    project = cycle.project
    workspace = project.workspace

    if cycle.start_date is None or cycle.end_date is None:
        return {"ready": False, "reason": "cycle_has_no_dates", "members": []}

    start = cycle.start_date.date() if hasattr(cycle.start_date, "date") else cycle.start_date
    end = cycle.end_date.date() if hasattr(cycle.end_date, "date") else cycle.end_date

    allocations = {
        row.member_id: row.allocation_percent
        for row in MemberProjectAllocation.objects.filter(workspace=workspace, project=project)
    }
    member_ids = list(allocations) or list(
        ProjectMember.objects.filter(project=project, is_active=True).values_list("member_id", flat=True)
    )
    allocation_is_assumed = not allocations

    profiles = {
        profile.member_id: profile
        for profile in MemberWorkProfile.objects.filter(workspace=workspace, member_id__in=member_ids)
        .select_related("work_calendar")
    }
    default_cal = default_calendar(workspace.id)
    occupancy = member_occupancy(
        workspace=workspace, start=start, end=end, member_ids=[str(v) for v in member_ids], capacity_only=True
    )

    overrides_cache: dict = {}
    rows = []
    for member_id in member_ids:
        profile = profiles.get(member_id)
        calendar = resolve_calendar(profile, workspace.id, default=default_cal)
        key = calendar.id if calendar else None
        if key not in overrides_cache:
            overrides_cache[key] = calendar_overrides(calendar, start, end)

        days = working_days(calendar, start, end, overrides_cache[key])
        hours_per_day = Decimal(profile.hours_per_day) if profile else Decimal(0)
        share = Decimal(allocations.get(member_id, 100)) / FULL_ALLOCATION
        away = occupancy.get(str(member_id), {})

        gross = Decimal(len(days)) * hours_per_day
        lost = sum((away[day].fraction for day in days if day in away), Decimal(0)) * hours_per_day
        available = (gross - lost) * share

        rows.append(
            {
                "member_id": str(member_id),
                "allocation_percent": allocations.get(member_id, 100),
                "working_days": len(days),
                "hours_per_day": _round(hours_per_day),
                "gross_hours": _round(gross * share),
                "absence_hours": _round(lost * share),
                "available_hours": _round(available),
                "declared": profile is not None,
            }
        )

    total = sum(Decimal(str(row["available_hours"])) for row in rows)
    committed = _committed_hours(project, cycle)

    return {
        "ready": True,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "members": rows,
        "available_hours": _round(total),
        "allocation_is_assumed": allocation_is_assumed,
        "undeclared_members": [row["member_id"] for row in rows if not row["declared"]],
        **committed,
    }


def _committed_hours(project, cycle):
    """Committed work, but only when the project estimates in time.

    A project on story points gets `comparable: False` and no number. Dividing points by
    hours would produce a ratio that reads like a fact.
    """
    estimate = Estimate.objects.filter(project=project, last_used=True).first()
    if estimate is None or estimate.type != EstimateType.TIME:
        return {
            "committed_comparable": False,
            "committed_hours": None,
            "estimate_type": estimate.type if estimate else None,
        }

    values = {
        point.id: _numeric(point.value)
        for point in EstimatePoint.objects.filter(estimate=estimate)
    }
    total = Decimal(0)
    for point_id in Issue.objects.filter(
        issue_cycle__cycle=cycle, estimate_point__isnull=False
    ).values_list("estimate_point_id", flat=True):
        total += values.get(point_id, Decimal(0))

    return {
        "committed_comparable": True,
        "committed_hours": _round(total),
        "estimate_type": EstimateType.TIME,
    }


def _numeric(value):
    try:
        return Decimal(str(value))
    except Exception:
        # An estimate point's value is free text; one that is not a number contributes
        # nothing rather than blowing up the whole panel.
        return Decimal(0)
