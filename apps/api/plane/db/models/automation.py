# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Rules that act on a work item when something happens to it.

Deliberately a narrow engine. The trigger is a state-group change and nothing else, and the
actions are a fixed set of field writes -- not an expression language. A general rule engine
in a project tracker is a way to build a second, undebuggable copy of the product's logic,
and the failure mode is a rule nobody can explain firing at 3am.

Two properties matter more than expressiveness:

- **Actions cannot trigger further rules.** Applying a rule writes fields directly rather
  than going through the path that evaluates rules, so a pair of rules that undo each other
  cannot loop. That is a design constraint, not a runtime guard, and it is why the action set
  is fixed rather than open.
- **A rule that cannot apply is skipped, not retried.** An action naming a deleted state
  drops, like a template payload, because a project that has been tidied should not start
  failing every save.
"""

from django.db import models
from django.db.models import Q

from .project import ProjectBaseModel


class Automation(ProjectBaseModel):
    class Trigger(models.TextChoices):
        # Fires when a work item lands in a state whose group is `trigger_state_group`.
        STATE_GROUP_ENTERED = "state_group_entered", "State group entered"

    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    trigger = models.CharField(max_length=40, choices=Trigger.choices, default=Trigger.STATE_GROUP_ENTERED)
    trigger_state_group = models.CharField(max_length=30)
    # A fixed shape, not an expression: {"priority": "...", "assignee_ids": [...], "label_ids": [...]}
    actions = models.JSONField(default=dict)

    class Meta:
        verbose_name = "Automation"
        verbose_name_plural = "Automations"
        db_table = "automations"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["project", "name"],
                condition=Q(deleted_at__isnull=True),
                name="automation_unique_name_project_when_active",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.trigger_state_group})"
