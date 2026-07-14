# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from rest_framework import serializers


class AutomationResultSerializer(serializers.Serializer):
    external_id = serializers.CharField(max_length=500)
    title = serializers.CharField(max_length=500, required=False)
    test_case_id = serializers.UUIDField(required=False)
    status = serializers.CharField(max_length=20)
    duration_ms = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    actual_result = serializers.JSONField(required=False, default=dict)


class AutomationIngestionSerializer(serializers.Serializer):
    source = serializers.CharField(max_length=100, default="ci")
    name = serializers.CharField(max_length=255)
    build = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    configuration = serializers.JSONField(required=False, default=dict)
    format = serializers.ChoiceField(choices=("results", "junit"), default="results")
    results = AutomationResultSerializer(many=True, required=False)
    junit_xml = serializers.CharField(required=False, trim_whitespace=False)
    artifact_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)

    def validate(self, attrs):
        if attrs["format"] == "junit" and not attrs.get("junit_xml"):
            raise serializers.ValidationError({"junit_xml": "This field is required for JUnit ingestion."})
        if attrs["format"] == "results" and not attrs.get("results"):
            raise serializers.ValidationError({"results": "At least one result is required."})
        return attrs
