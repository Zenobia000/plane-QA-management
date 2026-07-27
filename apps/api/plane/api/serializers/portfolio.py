# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from plane.db.models import Initiative, Milestone

from .base import BaseSerializer


class MilestoneSerializer(BaseSerializer):
    class Meta:
        model = Milestone
        fields = [
            "id",
            "name",
            "description",
            "target_date",
            "status",
            "sort_order",
            "project",
            "workspace",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "project", "workspace", "created_at", "updated_at"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name cannot be empty.")
        return value


class InitiativeSerializer(BaseSerializer):
    project_ids = serializers.ListField(child=serializers.UUIDField(), required=False, write_only=True)
    projects = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Initiative
        fields = [
            "id",
            "name",
            "description",
            "status",
            "target_date",
            "sort_order",
            "projects",
            "project_ids",
            "workspace",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "workspace", "created_at", "updated_at"]

    def get_projects(self, initiative):
        return [
            {"id": str(link.project_id), "name": link.project.name, "identifier": link.project.identifier}
            for link in initiative.initiative_projects.select_related("project").filter(deleted_at__isnull=True)
        ]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name cannot be empty.")
        return value
