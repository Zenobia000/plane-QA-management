# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Composable widgets over workspace data.

A widget stores a *question*, not an answer: which entity, grouped by what, filtered how.
Nothing is precomputed, because a dashboard that caches counts is a dashboard that is wrong
between refreshes, and every question here is a single indexed aggregate over tables the
work-item list already queries constantly.

`AnalyticView` exists and is a different, older concept -- a saved set of filters for the
analytics page. It is left alone rather than extended, because widening it into a widget
would change what every existing saved analytic view means.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

from .base import BaseModel


class Dashboard(BaseModel):
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="dashboards")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dashboards",
        null=True,
    )
    # Same Private/Public spelling `IssueView.access` uses, so one mental model covers both.
    access = models.PositiveSmallIntegerField(choices=((0, "Private"), (1, "Public")), default=1)

    class Meta:
        verbose_name = "Dashboard"
        verbose_name_plural = "Dashboards"
        db_table = "dashboards"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "name"],
                condition=Q(deleted_at__isnull=True),
                name="dashboard_unique_name_workspace_when_active",
            )
        ]

    def __str__(self):
        return self.name


class DashboardWidget(BaseModel):
    class Entity(models.TextChoices):
        WORK_ITEM = "work_item", "Work item"

    class GroupBy(models.TextChoices):
        STATE_GROUP = "state_group", "State group"
        PRIORITY = "priority", "Priority"
        ASSIGNEE = "assignee", "Assignee"
        PROJECT = "project", "Project"

    class Chart(models.TextChoices):
        BAR = "bar", "Bar"
        DONUT = "donut", "Donut"
        NUMBER = "number", "Number"

    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE, related_name="widgets")
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="dashboard_widgets")
    name = models.CharField(max_length=255)
    entity = models.CharField(max_length=30, choices=Entity.choices, default=Entity.WORK_ITEM)
    group_by = models.CharField(max_length=30, choices=GroupBy.choices, default=GroupBy.STATE_GROUP)
    chart = models.CharField(max_length=30, choices=Chart.choices, default=Chart.BAR)
    # Scope, not display: which projects this widget counts over. Empty means all of them.
    project_ids = models.JSONField(default=list)
    sort_order = models.FloatField(default=65535)

    class Meta:
        verbose_name = "Dashboard Widget"
        verbose_name_plural = "Dashboard Widgets"
        db_table = "dashboard_widgets"
        ordering = ("sort_order", "created_at")

    def __str__(self):
        return f"{self.dashboard} / {self.name}"
