# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from plane.db.models import (
    FileAsset,
    ReleaseEvidence,
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
            "case_type",
            "threshold_metric",
            "threshold_operator",
            "threshold_value",
            "threshold_unit",
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
    work_items = serializers.SerializerMethodField()
    executions = serializers.SerializerMethodField()
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
            "work_items",
            "executions",
            "latest_status",
        ]
        read_only_fields = fields

    def get_current(self, instance):
        versions = list(instance.versions.all())
        current = next((item for item in versions if item.version == instance.current_version), None)
        return TestCaseVersionSerializer(current).data if current else None

    def get_work_item_ids(self, instance):
        return [str(link.issue_id) for link in instance.work_item_links.all()]

    def get_work_items(self, instance):
        """Identifier, name and state of each linked requirement.

        `work_item_ids` alone leaves the UI unable to say more than "1 linked
        item", which is why the traceability panel showed a bare count.
        """
        return [
            {
                "id": str(link.issue_id),
                "sequence_id": link.issue.sequence_id,
                "name": link.issue.name,
                "state_group": link.issue.state.group if link.issue.state else None,
            }
            for link in instance.work_item_links.all()
        ]

    def get_executions(self, instance):
        """Every run this case has appeared in, newest first.

        The case knew its latest status but not where that came from, so a
        failure could not be traced back to the run that produced it.
        """
        run_cases = sorted(
            instance.run_cases.all(),
            key=lambda item: item.test_run.created_at,
            reverse=True,
        )
        return [
            {
                "run_id": str(run_case.test_run_id),
                "run_case_id": str(run_case.id),
                "run_name": run_case.test_run.name,
                "build": run_case.test_run.build,
                "run_status": run_case.test_run.status,
                "pinned_version": run_case.test_case_version.version,
                "latest_status": run_case.latest_status,
                "executed_at": run_case.test_run.created_at,
            }
            for run_case in run_cases
        ]

    def get_latest_status(self, instance):
        latest = max(instance.run_cases.all(), key=lambda item: item.test_run.created_at, default=None)
        return latest.latest_status if latest else None


class TestCaseAttachmentSerializer(BaseSerializer):
    download_url = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()

    class Meta:
        model = FileAsset
        fields = [
            "id",
            "attributes",
            "size",
            "created_at",
            "created_by_id",
            "download_url",
            "preview_url",
        ]
        read_only_fields = fields

    def _asset_url(self, instance, *, preview=False):
        request = self.context.get("request")
        api_prefix = "/api/v1" if request and request.path.startswith("/api/v1/") else "/api"
        suffix = "?preview=true" if preview else ""
        return (
            f"{api_prefix}/workspaces/{instance.workspace.slug}/projects/{instance.project_id}/testing/"
            f"test-cases/{instance.entity_identifier}/attachments/{instance.id}/{suffix}"
        )

    def get_download_url(self, instance):
        return self._asset_url(instance)

    def get_preview_url(self, instance):
        mime_type = instance.attributes.get("type", "")
        return self._asset_url(instance, preview=True) if mime_type.startswith("image/") else None


class TestStepInputSerializer(serializers.Serializer):
    action = serializers.JSONField()
    expected_result = serializers.JSONField(required=False, default=dict)


class TestCaseWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=500, allow_blank=False, trim_whitespace=True)
    folder_id = serializers.UUIDField(required=False, allow_null=True)
    description = serializers.JSONField(required=False, default=dict)
    preconditions = serializers.JSONField(required=False, default=dict)
    priority = serializers.ChoiceField(choices=TestCaseVersion.PRIORITY_CHOICES, required=False, default="none")
    case_type = serializers.ChoiceField(choices=TestCaseVersion.CASE_TYPE_CHOICES, required=False, default="functional")
    threshold_metric = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    threshold_operator = serializers.ChoiceField(
        choices=TestCaseVersion.THRESHOLD_OPERATOR_CHOICES, required=False, allow_blank=True, default=""
    )
    threshold_value = serializers.DecimalField(
        max_digits=20, decimal_places=6, required=False, allow_null=True, default=None
    )
    threshold_unit = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    tags = serializers.ListField(child=serializers.CharField(max_length=100), required=False, default=list)
    steps = TestStepInputSerializer(many=True, required=False, default=list)

    def validate(self, attrs):
        """Reject a half-stated threshold here as well as at the model.

        The model's `clean` is the guarantee; this is the message. A `ValidationError`
        raised from `full_clean` inside the service surfaces as a 500-shaped failure
        rather than a 400 naming the field, and the caller most likely to get this wrong
        is a script filling in three of four keys.
        """
        present = [
            bool(attrs.get("threshold_metric")),
            bool(attrs.get("threshold_operator")),
            attrs.get("threshold_value") is not None,
        ]
        if any(present) and not all(present):
            raise serializers.ValidationError(
                {
                    "threshold_metric": "A threshold needs a metric, an operator and a value together, "
                    "or none of the three."
                }
            )
        if attrs.get("threshold_unit") and not any(present):
            raise serializers.ValidationError(
                {"threshold_unit": "A threshold unit means nothing without a metric, an operator and a value."}
            )
        return attrs


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


class ReleaseEvidenceSerializer(BaseSerializer):
    class Meta:
        model = ReleaseEvidence
        fields = ["id", "kind", "key", "name", "status", "detail", "source_url", "recorded_at"]
        read_only_fields = ["id", "recorded_at"]


class ReleaseEvidenceWriteSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=ReleaseEvidence.KIND_CHOICES)
    key = serializers.CharField(max_length=120)
    name = serializers.CharField(max_length=255)
    status = serializers.ChoiceField(choices=ReleaseEvidence.STATUS_CHOICES, default="pending")
    detail = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    source_url = serializers.URLField(max_length=800, required=False, allow_blank=True, default="")
