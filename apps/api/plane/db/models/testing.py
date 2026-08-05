# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.exceptions import ValidationError
from django.db import models

from plane.db.soft_delete import is_soft_delete_save

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
    # How the contract is verified, not what kind of requirement it answers for.
    # A functional requirement can carry a performance threshold among its
    # acceptance conditions, so this never doubles as an FR/NFR classification --
    # that lives on the work item.
    CASE_TYPE_CHOICES = (
        ("functional", "Functional"),
        ("performance", "Performance"),
        ("security", "Security"),
        ("reliability", "Reliability"),
        ("compliance", "Compliance"),
    )

    # The comparison a quality requirement is judged by. `case_type` already says the
    # contract is verified by measuring; these say what is measured and what number
    # decides it.
    #
    # Without them a threshold has only ever had free text to live in, so "P95 < 2s"
    # was a sentence in the description: readable by a person, and unreadable by any
    # report. Nothing here evaluates a result against the threshold -- recording a
    # verdict is still the caller's statement -- but the number is now a number, which
    # is what a trend or an automatic judgement would need first.
    THRESHOLD_OPERATOR_CHOICES = (
        ("lt", "Less than"),
        ("lte", "At most"),
        ("gt", "Greater than"),
        ("gte", "At least"),
    )

    test_case = models.ForeignKey(TestCase, on_delete=models.CASCADE, related_name="versions")
    version = models.PositiveIntegerField()
    title = models.CharField(max_length=500)
    description = models.JSONField(default=dict, blank=True)
    preconditions = models.JSONField(default=dict, blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="none")
    case_type = models.CharField(max_length=20, choices=CASE_TYPE_CHOICES, default="functional")
    # What is measured, in the project's own words -- "checkout P95 latency", "monthly
    # availability". Not a closed vocabulary: the metric names a team uses come from its
    # own monitoring, and a list compiled into the product would be wrong everywhere.
    threshold_metric = models.CharField(max_length=255, blank=True)
    threshold_operator = models.CharField(max_length=8, choices=THRESHOLD_OPERATOR_CHOICES, blank=True)
    # Decimal rather than float: these are compared and shown, and a threshold that reads
    # 1.9999999999 in a report is the kind of thing nobody trusts twice.
    threshold_value = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    # Optional where the other three are not. A ratio or a count is dimensionless, and
    # forcing a unit on it invites "count" as a unit, which says nothing.
    threshold_unit = models.CharField(max_length=32, blank=True)
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

    def clean(self):
        # Metric, operator and value stand or fall together. Two of the three is not a
        # weaker threshold, it is an unreadable one: a number with no comparison cannot
        # be judged, and a comparison with no number cannot be met. Storing the fragment
        # would put the report back to guessing, which is the state this field exists to
        # end. The unit is exempt because a ratio or a count genuinely has none.
        present = [
            bool(self.threshold_metric),
            bool(self.threshold_operator),
            self.threshold_value is not None,
        ]
        if any(present) and not all(present):
            raise ValidationError(
                "A threshold needs a metric, an operator and a value together, or none of the three."
            )
        if self.threshold_unit and not any(present):
            raise ValidationError("A threshold unit means nothing without a metric, an operator and a value.")

    def save(self, *args, **kwargs):
        # Immutability is about the content of a published version, not its lifetime. A
        # soft delete names only the lifecycle columns and is allowed through; without that
        # exemption a version outlives the project that owned it, unreachable but alive.
        if not self._state.adding and not is_soft_delete_save(kwargs):
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
        # See TestCaseVersion.save: retiring a row is not editing it.
        if not self._state.adding and not is_soft_delete_save(kwargs):
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
        # See TestCaseVersion.save: append-only governs what a result says, not whether the
        # row survives the project it was recorded in.
        if not self._state.adding and not is_soft_delete_save(kwargs):
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


class ReleaseEvidence(ProjectBaseModel):
    """Evidence for a release decision that testing cannot produce.

    Availability is last month's measurement and a recovery objective is proved
    by a drill; neither can be executed before shipping, so forcing them into a
    test case yields a case that runs daily while representing no test. They are
    recorded here instead and consulted by the release gate alongside run results.
    """

    KIND_CHOICES = (
        ("slo", "Service level objective"),
        ("scan", "Security or compliance scan"),
        ("review", "Review or sign-off"),
        ("other", "Other"),
    )
    STATUS_CHOICES = (("passing", "Passing"), ("failing", "Failing"), ("pending", "Pending"))

    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    # Stable per project, so a repeated submission updates the same row rather
    # than accumulating a history of duplicates in the gate.
    key = models.CharField(max_length=120)
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    detail = models.CharField(max_length=500, blank=True, default="")
    source_url = models.URLField(max_length=800, blank=True, default="")
    recorded_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "test_release_evidence"
        ordering = ("kind", "name")
        constraints = [
            models.UniqueConstraint(
                fields=["project", "key"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_release_evidence_key",
            )
        ]


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
