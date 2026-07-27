# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import models
from django.db.models import Q

from .project import ProjectBaseModel


class WorkItemProperty(ProjectBaseModel):
    """A project-scoped custom field definition for work items."""

    class Kind(models.TextChoices):
        TEXT = "text", "Text"
        NUMBER = "number", "Number"
        DATE = "date", "Date"
        BOOLEAN = "boolean", "Boolean"
        SELECT = "select", "Select"
        MULTI_SELECT = "multi_select", "Multi select"
        URL = "url", "URL"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    kind = models.CharField(max_length=32, choices=Kind.choices)
    is_required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.FloatField(default=65535)
    default_value = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "work_item_properties"
        ordering = ("sort_order", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=["project", "name"],
                condition=Q(deleted_at__isnull=True),
                name="work_item_property_unique_name_project_when_active",
            )
        ]


class WorkItemPropertyOption(ProjectBaseModel):
    """An ordered option for a single or multi-select work-item property."""

    property = models.ForeignKey(WorkItemProperty, on_delete=models.CASCADE, related_name="options")
    label = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    sort_order = models.FloatField(default=65535)

    class Meta:
        db_table = "work_item_property_options"
        ordering = ("sort_order", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=["property", "value"],
                condition=Q(deleted_at__isnull=True),
                name="work_item_property_option_unique_value_when_active",
            )
        ]


class WorkItemPropertyValue(ProjectBaseModel):
    """A typed JSON value for one property on one work item."""

    property = models.ForeignKey(WorkItemProperty, on_delete=models.CASCADE, related_name="values")
    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="property_values")
    value = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "work_item_property_values"
        constraints = [
            models.UniqueConstraint(
                fields=["issue", "property"],
                condition=Q(deleted_at__isnull=True),
                name="work_item_property_value_unique_issue_property_when_active",
            )
        ]
