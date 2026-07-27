# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import models
from django.db.models import Q

from .base import BaseModel
from .project import ProjectBaseModel


class Milestone(ProjectBaseModel):
    """A project delivery checkpoint that can contain many work items."""

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    target_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PLANNED)
    sort_order = models.FloatField(default=65535)

    class Meta:
        db_table = "milestones"
        ordering = ("target_date", "sort_order", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=["project", "name"],
                condition=Q(deleted_at__isnull=True),
                name="milestone_unique_name_project_when_active",
            )
        ]


class Initiative(BaseModel):
    """A workspace-level strategic outcome spanning one or more projects."""

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="initiatives")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PLANNED)
    target_date = models.DateField(null=True, blank=True)
    sort_order = models.FloatField(default=65535)

    class Meta:
        db_table = "initiatives"
        ordering = ("target_date", "sort_order", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "name"],
                condition=Q(deleted_at__isnull=True),
                name="initiative_unique_name_workspace_when_active",
            )
        ]


class InitiativeProject(BaseModel):
    """An initiative's project membership, deliberately scoped to the same workspace."""

    initiative = models.ForeignKey(Initiative, on_delete=models.CASCADE, related_name="initiative_projects")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="project_initiatives")
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="workspace_initiative_projects")

    class Meta:
        db_table = "initiative_projects"
        constraints = [
            models.UniqueConstraint(
                fields=["initiative", "project"],
                condition=Q(deleted_at__isnull=True),
                name="initiative_project_unique_when_active",
            )
        ]
