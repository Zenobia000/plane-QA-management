# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db import models
from django.template.defaultfilters import slugify
from django.db.models import Q

# Module imports
from .project import ProjectBaseModel
from plane.db.mixins import SoftDeletionManager

class StateGroup(models.TextChoices):
    BACKLOG = "backlog", "Backlog"
    UNSTARTED = "unstarted", "Unstarted"
    STARTED = "started", "Started"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"
    TRIAGE = "triage", "Triage"


# Default states
DEFAULT_STATES = [
    {
        "name": "Backlog",
        "color": "#60646C",
        "sequence": 15000,
        "group": StateGroup.BACKLOG.value,
        "default": True,
    },
    {
        "name": "Todo",
        "color": "#60646C",
        "sequence": 25000,
        "group": StateGroup.UNSTARTED.value,
    },
    {
        "name": "In Progress",
        "color": "#F59E0B",
        "sequence": 35000,
        "group": StateGroup.STARTED.value,
    },
    {
        "name": "Done",
        "color": "#46A758",
        "sequence": 45000,
        "group": StateGroup.COMPLETED.value,
    },
    {
        "name": "Cancelled",
        "color": "#9AA4BC",
        "sequence": 55000,
        "group": StateGroup.CANCELLED.value,
    },
    {
        "name": "Triage",
        "color": "#4E5355",
        "sequence": 65000,
        "group": StateGroup.TRIAGE.value,
    },
]


# The delivery process from `docs/process/plane-qa-guideline.md` and the eleven stages in
# the portable `sdlc-guideline.md`, expressed as states a board can show. `DEFAULT_STATES`
# above collapses all eleven into one `In Progress`, so the process this project documents
# most carefully was the one its board could not display: nothing distinguished "waiting on
# code review" from "waiting on QA" from "verified and waiting to ship".
#
# `group` is not decoration. Four separate readers key off it, and the mapping below was
# chosen against them rather than against how the columns look:
#
# - `requirement_coverage` treats every group except `backlog` and `cancelled` as owing an
#   acceptance contract (`report.py:28`). `Next Sprint` is therefore the first state that
#   demands one, which is where Definition of Ready belongs
# - the release gate counts a defect as open while its group is neither `completed` nor
#   `cancelled` (`report.py:150-159`). This is why `Wait to Release` sits in `started`: a
#   defect parked there is not resolved, and grouping it as `completed` would quietly stop
#   it blocking the gate
# - `Issue._sync_completed_at` stamps `completed_at` on entry to `completed`
# - cycle progress reads `(completed + cancelled) / total`, so anything grouped `completed`
#   counts as delivered on the burndown
#
# Two states from the reference design are deliberately absent, both because they describe
# something other than progress and modelling them here would collapse two axes -- the
# mistake `plane/testing/demo/scaffolding.py` opens by warning against:
#
# - **Resident** is standing operational work that never closes. As a `completed` state it
#   would inflate every burndown; as a `started` state it would sit in WIP forever; and
#   excluding it inside coverage would create a second definition of "in scope" that drifts
#   from the gate's. It is a kind of work, not a stage, so the seed carries it as a label
# - **Archived** already exists as a mechanism. `Issue.archived_at`, the `/archives/issues`
#   route and `plane/app/views/issue/archive.py` implement it orthogonally to state, and a
#   state of the same name would give one concept two homes
# `Todo` is the one addition to the reference set. That design leans on its board grouping
# for the waiting cases -- one column per sprint plus a "no sprint" bucket -- so it never
# needed a state meaning "committed to the sprint we are in, nobody has picked it up". A
# real sprint always holds some of those, and without it the Definition-of-Ready example
# has nowhere to sit: an item scheduled into the current sprint with no acceptance contract
# is the case the release gate exists to catch, and calling it `Next Sprint` would deny the
# very scheduling that makes it a violation. Both it and `Next Sprint` group `unstarted`,
# so both owe a contract; they differ only in which sprint made the commitment.
SDLC_STATES = [
    {"name": "Backlog", "color": "#60646C", "sequence": 15000, "group": StateGroup.BACKLOG.value, "default": True},
    {"name": "Next Sprint", "color": "#8B8D98", "sequence": 30000, "group": StateGroup.UNSTARTED.value},
    {"name": "Todo", "color": "#60646C", "sequence": 45000, "group": StateGroup.UNSTARTED.value},
    {"name": "Planning", "color": "#6366F1", "sequence": 60000, "group": StateGroup.STARTED.value},
    {"name": "In Design", "color": "#EAB308", "sequence": 75000, "group": StateGroup.STARTED.value},
    {"name": "In progress", "color": "#F59E0B", "sequence": 90000, "group": StateGroup.STARTED.value},
    {"name": "In developing", "color": "#F97316", "sequence": 105000, "group": StateGroup.STARTED.value},
    {"name": "PR Reviewing", "color": "#A855F7", "sequence": 120000, "group": StateGroup.STARTED.value},
    {"name": "In Diversity Testing", "color": "#8B5CF6", "sequence": 135000, "group": StateGroup.STARTED.value},
    {"name": "PM Retest", "color": "#C084FC", "sequence": 150000, "group": StateGroup.STARTED.value},
    {"name": "Pending", "color": "#CA8A04", "sequence": 165000, "group": StateGroup.STARTED.value},
    {"name": "Wait to Release", "color": "#EA580C", "sequence": 180000, "group": StateGroup.STARTED.value},
    {"name": "Done", "color": "#46A758", "sequence": 195000, "group": StateGroup.COMPLETED.value},
    {"name": "Canceled", "color": "#DC2626", "sequence": 210000, "group": StateGroup.CANCELLED.value},
    # Intake needs a triage state to exist even when the feature is switched off, and the
    # default manager hides it from every ordinary state query.
    {"name": "Triage", "color": "#4E5355", "sequence": 225000, "group": StateGroup.TRIAGE.value},
]


class StateManager(SoftDeletionManager):
    """Default manager - excludes triage states"""

    def get_queryset(self):
        return super().get_queryset().exclude(group=StateGroup.TRIAGE.value)


class TriageStateManager(SoftDeletionManager):
    """Manager for triage states only"""

    def get_queryset(self):
        return super().get_queryset().filter(group=StateGroup.TRIAGE.value)


class State(ProjectBaseModel):
    name = models.CharField(max_length=255, verbose_name="State Name")
    description = models.TextField(verbose_name="State Description", blank=True)
    color = models.CharField(max_length=255, verbose_name="State Color")
    slug = models.SlugField(max_length=100, blank=True)
    sequence = models.FloatField(default=65535)
    group = models.CharField(
        choices=StateGroup.choices,
        default=StateGroup.BACKLOG,
        max_length=20,
    )
    is_triage = models.BooleanField(default=False)
    default = models.BooleanField(default=False)
    external_source = models.CharField(max_length=255, null=True, blank=True)
    external_id = models.CharField(max_length=255, blank=True, null=True)

    objects = StateManager()
    all_state_objects = models.Manager()
    triage_objects = TriageStateManager()

    def __str__(self):
        """Return name of the state"""
        return f"{self.name} <{self.project.name}>"

    class Meta:
        unique_together = ["name", "project", "deleted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "project"],
                condition=Q(deleted_at__isnull=True),
                name="state_unique_name_project_when_deleted_at_null",
            )
        ]
        verbose_name = "State"
        verbose_name_plural = "States"
        db_table = "states"
        ordering = ("sequence",)

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        if self._state.adding:
            # Get the maximum sequence value from the database
            last_id = State.objects.filter(project=self.project).aggregate(largest=models.Max("sequence"))["largest"]
            # if last_id is not None
            if last_id is not None:
                self.sequence = last_id + 15000

        return super().save(*args, **kwargs)
