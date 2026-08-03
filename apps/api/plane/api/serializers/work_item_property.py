# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.validators import URLValidator
from django.utils.dateparse import parse_date
from rest_framework import serializers

from plane.db.models import WorkItemProperty, WorkItemPropertyOption, WorkItemPropertyValue

from .base import BaseSerializer


class WorkItemPropertyOptionSerializer(BaseSerializer):
    class Meta:
        model = WorkItemPropertyOption
        fields = ["id", "label", "value", "sort_order"]
        read_only_fields = ["id"]


class WorkItemPropertySerializer(BaseSerializer):
    options = WorkItemPropertyOptionSerializer(many=True, required=False)

    class Meta:
        model = WorkItemProperty
        fields = [
            "id",
            "name",
            "description",
            "kind",
            "is_required",
            "is_active",
            "is_grouping_dimension",
            "sort_order",
            "default_value",
            "options",
            "type",
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

    def validate(self, data):
        kind = data.get("kind", getattr(self.instance, "kind", None))
        options = data.get("options")
        if kind in {WorkItemProperty.Kind.SELECT, WorkItemProperty.Kind.MULTI_SELECT} and options is not None:
            option_values = [option["value"] for option in options]
            if len(option_values) != len(set(option_values)):
                raise serializers.ValidationError({"options": "Option values must be unique."})
        if kind not in {WorkItemProperty.Kind.SELECT, WorkItemProperty.Kind.MULTI_SELECT} and options:
            raise serializers.ValidationError({"options": "Only select properties can define options."})
        return data

    def validate_is_grouping_dimension(self, value):
        """Only a select-like property can group anything.

        Grouping by free text produces one bucket per typo, and grouping by a date or a
        checkbox produces buckets nobody asked for. The options list is what makes the
        panel's rows a fixed, meaningful set.
        """
        kind = self.initial_data.get("kind") or getattr(self.instance, "kind", None)
        if value and kind not in {WorkItemProperty.Kind.SELECT, WorkItemProperty.Kind.MULTI_SELECT}:
            raise serializers.ValidationError("Only a select or multi-select property can be the grouping dimension.")
        return value

    def create(self, validated_data):
        options = validated_data.pop("options", [])
        property_definition = super().create(validated_data)
        self._replace_options(property_definition, options)
        return property_definition

    def update(self, instance, validated_data):
        options = validated_data.pop("options", None)
        property_definition = super().update(instance, validated_data)
        if options is not None:
            self._replace_options(property_definition, options)
        return property_definition

    @staticmethod
    def _replace_options(property_definition, options):
        if options is None:
            return
        WorkItemPropertyOption.objects.filter(property=property_definition).delete()
        WorkItemPropertyOption.objects.bulk_create(
            [
                WorkItemPropertyOption(
                    property=property_definition,
                    project=property_definition.project,
                    workspace=property_definition.workspace,
                    **option,
                )
                for option in options
            ]
        )


def validate_property_value(property_definition: WorkItemProperty, value):
    """Validate a JSON value against its field definition before it is persisted."""

    if value is None:
        if property_definition.is_required:
            raise serializers.ValidationError({"value": "This work item property is required."})
        return value

    kind = property_definition.kind
    if kind == WorkItemProperty.Kind.TEXT:
        if not isinstance(value, str):
            raise serializers.ValidationError({"value": "Expected a text value."})
    elif kind == WorkItemProperty.Kind.NUMBER:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise serializers.ValidationError({"value": "Expected a numeric value."})
    elif kind == WorkItemProperty.Kind.BOOLEAN:
        if not isinstance(value, bool):
            raise serializers.ValidationError({"value": "Expected a boolean value."})
    elif kind == WorkItemProperty.Kind.DATE:
        if not isinstance(value, str) or parse_date(value) is None:
            raise serializers.ValidationError({"value": "Expected an ISO-8601 date value."})
    elif kind == WorkItemProperty.Kind.URL:
        if not isinstance(value, str):
            raise serializers.ValidationError({"value": "Expected a URL value."})
        try:
            URLValidator(schemes=["http", "https"])(value)
        except Exception as exc:
            raise serializers.ValidationError({"value": "Expected a valid HTTP(S) URL."}) from exc
    elif kind == WorkItemProperty.Kind.SELECT:
        if not isinstance(value, str):
            raise serializers.ValidationError({"value": "Expected one option value."})
        if not property_definition.options.filter(value=value, deleted_at__isnull=True).exists():
            raise serializers.ValidationError({"value": "Selected option is not available."})
    elif kind == WorkItemProperty.Kind.MULTI_SELECT:
        if not isinstance(value, list) or not all(isinstance(option, str) for option in value):
            raise serializers.ValidationError({"value": "Expected a list of option values."})
        if len(value) != len(set(value)):
            raise serializers.ValidationError({"value": "Option values must be unique."})
        available = set(property_definition.options.filter(deleted_at__isnull=True).values_list("value", flat=True))
        if not set(value).issubset(available):
            raise serializers.ValidationError({"value": "One or more selected options are not available."})
    return value


class WorkItemPropertyValueSerializer(BaseSerializer):
    property = WorkItemPropertySerializer(read_only=True)

    class Meta:
        model = WorkItemPropertyValue
        fields = ["id", "property", "value", "issue", "project", "workspace", "created_at", "updated_at"]
        read_only_fields = ["id", "property", "issue", "project", "workspace", "created_at", "updated_at"]
