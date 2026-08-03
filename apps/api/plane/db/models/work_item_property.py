# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import models
from django.db.models import Q

from .project import ProjectBaseModel


class WorkItemProperty(ProjectBaseModel):
    """A custom field definition for work items, optionally narrowed to one work item type.

    `type` null means the property applies to every work item in the project, which is what
    every property created before this field existed does and what the plain case still is.
    Setting it narrows the property to one type -- a Severity that only Bugs carry, or a
    Business Value that only Epics do -- which is how upstream EE scopes properties and the
    reason an epic could not have a field of its own here before.

    Narrowing affects who is *asked* for a value, not what is stored: a value already
    recorded against a work item survives the property being narrowed away from that item's
    type, because deleting user data to satisfy a settings change would be the worse of the
    two surprises. Such a value stops being rendered and stops being required.
    """

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
    # The one property the project overview groups its intake panel by.
    #
    # Which dimension a team cares about is a product decision, not ours: for one project
    # it is the customer, for another the tenant, the region or the pilot cohort. Marking
    # a property instead of naming one in code means the label on the panel is whatever
    # the team typed into settings, and no category name is compiled into the product.
    #
    # Project-level rather than per-viewer because everyone reading the overview should be
    # looking at the same board.
    is_grouping_dimension = models.BooleanField(default=False)
    sort_order = models.FloatField(default=65535)
    default_value = models.JSONField(null=True, blank=True)
    type = models.ForeignKey(
        "db.IssueType",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="work_item_properties",
    )

    class Meta:
        db_table = "work_item_properties"
        ordering = ("sort_order", "created_at")
        # Two constraints rather than one over (project, type, name), because Postgres treats
        # NULLs as distinct in a unique index: a single constraint would let a project hold
        # any number of untyped properties all called "Severity", which is exactly what the
        # original constraint existed to prevent. The pair keeps that guarantee for untyped
        # properties while letting Bug and Epic each carry their own "Severity".
        constraints = [
            models.UniqueConstraint(
                fields=["project", "name"],
                condition=Q(deleted_at__isnull=True, type__isnull=True),
                name="work_item_property_unique_name_project_when_active",
            ),
            models.UniqueConstraint(
                fields=["project", "type", "name"],
                condition=Q(deleted_at__isnull=True, type__isnull=False),
                name="work_item_property_unique_name_project_type_when_active",
            ),
            # One dimension per project. Two would mean the panel silently picking a
            # winner, and the loser's owner wondering why their choice did nothing.
            models.UniqueConstraint(
                fields=["project"],
                condition=Q(deleted_at__isnull=True, is_grouping_dimension=True),
                name="work_item_property_one_grouping_dimension_per_project",
            ),
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
