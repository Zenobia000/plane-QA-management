# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Saved shapes to create things from.

One model for work-item and project templates rather than two, for the same reason
`EntityUpdate` is one model: the two differ only in what the payload describes, and building
them separately means writing the listing, the permissions and the apply path twice.

`payload` is deliberately a bare JSON blob and deliberately not validated against the target
serializer at save time. A template outlives the schema it was written against -- a saved
work item naming a state that has since been deleted must still be openable so somebody can
fix it, rather than 500 on read. Application resolves what it can and drops what it cannot,
which is the only behaviour that stays useful as a project changes.

A project template is workspace-scoped, so `project` is null for those. That is the one place
this model cannot be a `ProjectBaseModel`.
"""

from django.db import models
from django.db.models import Q

from .base import BaseModel


class Template(BaseModel):
    class Kind(models.TextChoices):
        WORK_ITEM = "work_item", "Work item"
        PROJECT = "project", "Project"

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="templates")
    # Null for workspace-level templates, which is every project template.
    project = models.ForeignKey(
        "db.Project",
        on_delete=models.CASCADE,
        related_name="templates",
        null=True,
        blank=True,
    )
    kind = models.CharField(max_length=30, choices=Kind.choices)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    payload = models.JSONField(default=dict)

    class Meta:
        verbose_name = "Template"
        verbose_name_plural = "Templates"
        db_table = "templates"
        ordering = ("kind", "name")
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "kind", "name"],
                condition=Q(deleted_at__isnull=True),
                name="template_unique_name_per_kind_when_active",
            )
        ]

    def __str__(self):
        return f"{self.kind}:{self.name}"
