# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.exceptions import ValidationError
from django.db import models

from .project import ProjectBaseModel


class TestFolder(ProjectBaseModel):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
    )
    sort_order = models.FloatField(default=65535)

    class Meta:
        db_table = "test_folders"
        ordering = ("sort_order", "name")
        constraints = [
            models.UniqueConstraint(
                fields=["project", "parent", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_test_folder_name",
            )
        ]

    def clean(self):
        if self.parent_id and self.parent.project_id != self.project_id:
            raise ValidationError("A test folder parent must belong to the same project.")
        if self.parent_id == self.id:
            raise ValidationError("A test folder cannot be its own parent.")


class TestCase(ProjectBaseModel):
    folder = models.ForeignKey(
        TestFolder,
        on_delete=models.SET_NULL,
        related_name="test_cases",
        null=True,
        blank=True,
    )
    sequence = models.PositiveBigIntegerField()
    current_version = models.PositiveIntegerField(default=1)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "test_cases"
        ordering = ("sequence",)
        constraints = [
            models.UniqueConstraint(
                fields=["project", "sequence"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_test_case_sequence",
            )
        ]

    def clean(self):
        if self.folder_id and self.folder.project_id != self.project_id:
            raise ValidationError("A test case folder must belong to the same project.")


class TestCaseVersion(ProjectBaseModel):
    PRIORITY_CHOICES = (
        ("urgent", "Urgent"),
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
        ("none", "None"),
    )

    test_case = models.ForeignKey(TestCase, on_delete=models.CASCADE, related_name="versions")
    version = models.PositiveIntegerField()
    title = models.CharField(max_length=500)
    description = models.JSONField(default=dict, blank=True)
    preconditions = models.JSONField(default=dict, blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="none")
    tags = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "test_case_versions"
        ordering = ("-version",)
        constraints = [
            models.UniqueConstraint(
                fields=["test_case", "version"],
                name="unique_test_case_version",
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Published test case versions are immutable.")
        if self.test_case_id:
            self.project_id = self.test_case.project_id
            self.workspace_id = self.test_case.workspace_id
        super().save(*args, **kwargs)


class TestStep(ProjectBaseModel):
    test_case_version = models.ForeignKey(
        TestCaseVersion,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    position = models.PositiveIntegerField()
    action = models.JSONField(default=dict)
    expected_result = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "test_steps"
        ordering = ("position",)
        constraints = [
            models.UniqueConstraint(
                fields=["test_case_version", "position"],
                name="unique_test_step_position",
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Published test steps are immutable.")
        if self.test_case_version_id:
            self.project_id = self.test_case_version.project_id
            self.workspace_id = self.test_case_version.workspace_id
        super().save(*args, **kwargs)


class TestCaseWorkItemLink(ProjectBaseModel):
    test_case = models.ForeignKey(TestCase, on_delete=models.CASCADE, related_name="work_item_links")
    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="test_case_links")

    class Meta:
        db_table = "test_case_work_item_links"
        constraints = [
            models.UniqueConstraint(
                fields=["test_case", "issue"],
                name="unique_test_case_work_item_link",
            )
        ]

    def clean(self):
        if self.test_case.project_id != self.project_id or self.issue.project_id != self.project_id:
            raise ValidationError("Test case and work item links must stay within one project.")


class TestRun(ProjectBaseModel):
    STATUS_CHOICES = (("draft", "Draft"), ("active", "Active"), ("completed", "Completed"))
    TYPE_CHOICES = (("fixed", "Fixed"), ("live", "Live"))

    name = models.CharField(max_length=255)
    description = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    run_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="fixed")
    build = models.CharField(max_length=255, blank=True, default="")
    configuration = models.JSONField(default=dict, blank=True)
    cycle = models.ForeignKey(
        "db.Cycle", on_delete=models.SET_NULL, related_name="test_runs", null=True, blank=True
    )
    module = models.ForeignKey(
        "db.Module", on_delete=models.SET_NULL, related_name="test_runs", null=True, blank=True
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "test_runs"
        ordering = ("-created_at",)

    def clean(self):
        if self.cycle_id and self.cycle.project_id != self.project_id:
            raise ValidationError("A test run cycle must belong to the same project.")
        if self.module_id and self.module.project_id != self.project_id:
            raise ValidationError("A test run module must belong to the same project.")


class TestRunCase(ProjectBaseModel):
    STATUS_CHOICES = (
        ("open", "Open"),
        ("passed", "Passed"),
        ("failed", "Failed"),
        ("blocked", "Blocked"),
        ("skipped", "Skipped"),
    )

    test_run = models.ForeignKey(TestRun, on_delete=models.CASCADE, related_name="run_cases")
    test_case = models.ForeignKey(TestCase, on_delete=models.PROTECT, related_name="run_cases")
    test_case_version = models.ForeignKey(TestCaseVersion, on_delete=models.PROTECT, related_name="run_cases")
    position = models.PositiveIntegerField()
    latest_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")

    class Meta:
        db_table = "test_run_cases"
        ordering = ("position",)
        constraints = [
            models.UniqueConstraint(fields=["test_run", "test_case"], name="unique_test_case_per_run"),
            models.UniqueConstraint(fields=["test_run", "position"], name="unique_test_run_case_position"),
        ]

    def clean(self):
        project_ids = {
            self.project_id,
            self.test_run.project_id,
            self.test_case.project_id,
            self.test_case_version.project_id,
        }
        if len(project_ids) != 1 or self.test_case_version.test_case_id != self.test_case_id:
            raise ValidationError("A run case and its pinned version must belong to one test case and project.")


class TestResult(ProjectBaseModel):
    STATUS_CHOICES = tuple(choice for choice in TestRunCase.STATUS_CHOICES if choice[0] != "open")

    run_case = models.ForeignKey(TestRunCase, on_delete=models.CASCADE, related_name="results")
    sequence = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    actual_result = models.JSONField(default=dict, blank=True)
    duration_ms = models.PositiveBigIntegerField(null=True, blank=True)
    executed_by = models.ForeignKey(
        "db.User", on_delete=models.SET_NULL, related_name="test_results", null=True, blank=True
    )

    class Meta:
        db_table = "test_results"
        ordering = ("sequence",)
        constraints = [
            models.UniqueConstraint(fields=["run_case", "sequence"], name="unique_test_result_sequence")
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Test results are append-only.")
        if self.run_case_id:
            self.project_id = self.run_case.project_id
            self.workspace_id = self.run_case.workspace_id
        super().save(*args, **kwargs)


class TestResultIssueLink(ProjectBaseModel):
    test_result = models.ForeignKey(TestResult, on_delete=models.CASCADE, related_name="issue_links")
    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="test_result_links")

    class Meta:
        db_table = "test_result_issue_links"
        constraints = [
            models.UniqueConstraint(
                fields=["test_result", "issue"],
                name="unique_test_result_issue_link",
            )
        ]

    def clean(self):
        if self.test_result.project_id != self.project_id or self.issue.project_id != self.project_id:
            raise ValidationError("Test result and defect links must stay within one project.")


class TestCaseAutomationLink(ProjectBaseModel):
    test_case = models.ForeignKey(TestCase, on_delete=models.CASCADE, related_name="automation_links")
    source = models.CharField(max_length=100)
    external_id = models.CharField(max_length=500)

    class Meta:
        db_table = "test_case_automation_links"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "source", "external_id"],
                name="unique_test_case_automation_identity",
            )
        ]

    def clean(self):
        if self.test_case.project_id != self.project_id:
            raise ValidationError("Automation links must stay within the test case project.")


class TestAutomationIngestion(ProjectBaseModel):
    source = models.CharField(max_length=100)
    idempotency_key = models.CharField(max_length=255)
    payload_hash = models.CharField(max_length=64)
    test_run = models.OneToOneField(TestRun, on_delete=models.CASCADE, related_name="automation_ingestion")
    diagnostics = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "test_automation_ingestions"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "idempotency_key"],
                name="unique_test_automation_idempotency_key",
            )
        ]

    def clean(self):
        if self.test_run.project_id != self.project_id:
            raise ValidationError("An automation ingestion and its run must stay within one project.")
