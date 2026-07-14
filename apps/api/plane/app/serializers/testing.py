# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from plane.db.models import (
    TestCase,
    TestCaseVersion,
    TestCaseWorkItemLink,
    TestFolder,
    TestResult,
    TestResultIssueLink,
    TestRun,
    TestRunCase,
    TestStep,
)

from .base import BaseSerializer


class TestStepSerializer(BaseSerializer):
    class Meta:
        model = TestStep
        fields = ["id", "position", "action", "expected_result"]
        read_only_fields = fields


class TestCaseVersionSerializer(BaseSerializer):
    steps = TestStepSerializer(many=True, read_only=True)

    class Meta:
        model = TestCaseVersion
        fields = [
            "id",
            "version",
            "title",
            "description",
            "preconditions",
            "priority",
            "tags",
            "steps",
            "created_at",
            "created_by_id",
        ]
        read_only_fields = fields


class TestFolderSerializer(BaseSerializer):
    class Meta:
        model = TestFolder
        fields = ["id", "name", "parent_id", "sort_order", "created_at", "updated_at"]
        read_only_fields = fields


class TestCaseSerializer(BaseSerializer):
    current = serializers.SerializerMethodField()
    work_item_ids = serializers.SerializerMethodField()
    latest_status = serializers.SerializerMethodField()

    class Meta:
        model = TestCase
        fields = [
            "id",
            "sequence",
            "folder_id",
            "current_version",
            "archived_at",
            "created_at",
            "updated_at",
            "current",
            "work_item_ids",
            "latest_status",
        ]
        read_only_fields = fields

    def get_current(self, instance):
        versions = list(instance.versions.all())
        current = next((item for item in versions if item.version == instance.current_version), None)
        return TestCaseVersionSerializer(current).data if current else None

    def get_work_item_ids(self, instance):
        return [str(link.issue_id) for link in instance.work_item_links.all()]

    def get_latest_status(self, instance):
        latest = max(instance.run_cases.all(), key=lambda item: item.test_run.created_at, default=None)
        return latest.latest_status if latest else None


class TestStepInputSerializer(serializers.Serializer):
    action = serializers.JSONField()
    expected_result = serializers.JSONField(required=False, default=dict)


class TestCaseWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=500, allow_blank=False, trim_whitespace=True)
    folder_id = serializers.UUIDField(required=False, allow_null=True)
    description = serializers.JSONField(required=False, default=dict)
    preconditions = serializers.JSONField(required=False, default=dict)
    priority = serializers.ChoiceField(choices=TestCaseVersion.PRIORITY_CHOICES, required=False, default="none")
    tags = serializers.ListField(child=serializers.CharField(max_length=100), required=False, default=list)
    steps = TestStepInputSerializer(many=True, required=False, default=list)


class TestFolderWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True)
    parent_id = serializers.UUIDField(required=False, allow_null=True)
    sort_order = serializers.FloatField(required=False, default=65535)


class TestCaseWorkItemLinkSerializer(BaseSerializer):
    class Meta:
        model = TestCaseWorkItemLink
        fields = ["id", "test_case_id", "issue_id", "created_at"]
        read_only_fields = fields


class TestCaseWorkItemLinkWriteSerializer(serializers.Serializer):
    issue_id = serializers.UUIDField()


class TestDefectSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="issue.id", read_only=True)
    name = serializers.CharField(source="issue.name", read_only=True)
    sequence_id = serializers.IntegerField(source="issue.sequence_id", read_only=True)
    state_group = serializers.CharField(source="issue.state.group", read_only=True, allow_null=True)

    class Meta:
        model = TestResultIssueLink
        fields = ["id", "name", "sequence_id", "state_group", "created_at"]


class TestResultSerializer(BaseSerializer):
    defects = TestDefectSerializer(source="issue_links", many=True, read_only=True)

    class Meta:
        model = TestResult
        fields = [
            "id",
            "sequence",
            "status",
            "actual_result",
            "duration_ms",
            "executed_by_id",
            "created_at",
            "defects",
        ]
        read_only_fields = fields


class TestRunCaseSerializer(BaseSerializer):
    test_case_version = TestCaseVersionSerializer(read_only=True)
    results = TestResultSerializer(many=True, read_only=True)

    class Meta:
        model = TestRunCase
        fields = [
            "id",
            "test_case_id",
            "test_case_version",
            "position",
            "latest_status",
            "results",
        ]
        read_only_fields = fields


class TestRunSerializer(BaseSerializer):
    run_cases = TestRunCaseSerializer(many=True, read_only=True)
    progress = serializers.SerializerMethodField()

    class Meta:
        model = TestRun
        fields = [
            "id",
            "name",
            "description",
            "status",
            "run_type",
            "build",
            "configuration",
            "cycle_id",
            "module_id",
            "closed_at",
            "created_at",
            "updated_at",
            "progress",
            "run_cases",
        ]
        read_only_fields = fields

    def get_progress(self, instance):
        counts = {status: 0 for status, _label in TestRunCase.STATUS_CHOICES}
        for run_case in instance.run_cases.all():
            counts[run_case.latest_status] += 1
        return {"total": sum(counts.values()), **counts}


class TestRunWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True)
    description = serializers.JSONField(required=False, default=dict)
    build = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    configuration = serializers.JSONField(required=False, default=dict)
    cycle_id = serializers.UUIDField(required=False, allow_null=True)
    module_id = serializers.UUIDField(required=False, allow_null=True)
    test_case_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)


class TestResultWriteSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=TestResult.STATUS_CHOICES)
    actual_result = serializers.JSONField(required=False, default=dict)
    duration_ms = serializers.IntegerField(required=False, allow_null=True, min_value=0)


class TestDefectWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False, allow_blank=False, trim_whitespace=True)
    priority = serializers.ChoiceField(choices=("urgent", "high", "medium", "low", "none"), default="high")


class TestLibraryCSVImportSerializer(serializers.Serializer):
    csv_text = serializers.CharField(trim_whitespace=False, allow_blank=False)
