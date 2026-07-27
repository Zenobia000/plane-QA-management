# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from plane.db.models import IssueType, ProjectIssueType

from .base import BaseSerializer


class WorkItemTypeSerializer(BaseSerializer):
    """Workspace-wide work-item type definition."""

    class Meta:
        model = IssueType
        fields = [
            "id",
            "name",
            "description",
            "logo_props",
            "is_epic",
            "is_default",
            "is_active",
            "level",
            "external_source",
            "external_id",
            "workspace",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "workspace",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name cannot be empty.")
        return value


class ProjectWorkItemTypeSerializer(BaseSerializer):
    """A project's enablement and ordering of a workspace work-item type."""

    type = WorkItemTypeSerializer(source="issue_type", read_only=True)
    type_id = serializers.PrimaryKeyRelatedField(source="issue_type", queryset=IssueType.objects.all(), write_only=True)

    class Meta:
        model = ProjectIssueType
        fields = [
            "id",
            "type",
            "type_id",
            "level",
            "is_default",
            "project",
            "workspace",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "project", "workspace", "created_at", "updated_at"]

    def validate_type_id(self, issue_type):
        workspace_id = self.context.get("workspace_id")
        if not issue_type.is_active or str(issue_type.workspace_id) != str(workspace_id):
            raise serializers.ValidationError("Work item type is not available in this workspace.")
        return issue_type
