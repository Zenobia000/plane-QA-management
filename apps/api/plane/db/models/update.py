# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Status updates, for whichever entity is being reported on.

One model rather than one per entity. The official product shipped updates on epics first
and then extended them to every work item type and to projects, which is the shape you get
either way -- building `ProjectUpdate` and `WorkItemUpdate` separately would mean writing
the threading, the status vocabulary and the permission story twice and then reconciling
them. See ADR 0005.

The target is keyed the way `DeployBoard` already keys polymorphic entities in this
codebase: an `entity_name` from a fixed list plus an `entity_identifier` UUID. That costs
referential integrity on the target -- nothing at the database level stops an update
outliving the work item it describes -- so two things are the application's job:

- the serializer resolves `entity_identifier` inside the request's project before writing,
  so an update can never point across a project boundary
- deleting an entity removes its updates

Permissions come from `project`, never from the target. A reader who can see the project can
see its updates, which is the same rule every other `ProjectBaseModel` follows.
"""

from django.conf import settings
from django.db import models

from .choices import UpdateStatus
from .project import ProjectBaseModel


class EntityUpdate(ProjectBaseModel):
    class EntityName(models.TextChoices):
        PROJECT = "project", "Project"
        WORK_ITEM = "work_item", "Work item"

    Status = UpdateStatus

    entity_name = models.CharField(max_length=30, choices=EntityName.choices)
    entity_identifier = models.UUIDField()
    status = models.CharField(max_length=30, choices=UpdateStatus.choices, default=UpdateStatus.ON_TRACK)
    description = models.TextField(blank=True)
    # Replies, so a question about an update does not become a separate update.
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="replies",
        null=True,
        blank=True,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="entity_updates",
    )

    class Meta:
        verbose_name = "Entity Update"
        verbose_name_plural = "Entity Updates"
        db_table = "entity_updates"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["entity_name", "entity_identifier"], name="entity_update_target_idx"),
        ]

    def __str__(self):
        return f"{self.entity_name} {self.entity_identifier} {self.status}"
