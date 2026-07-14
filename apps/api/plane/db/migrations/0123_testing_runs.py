# Generated manually for the Plane native Testing domain on 2026-07-14.

import django.db.models.deletion
import uuid
from django.db import migrations, models


def base_fields():
    return [
        (
            "id",
            models.UUIDField(
                db_index=True,
                default=uuid.uuid4,
                editable=False,
                primary_key=True,
                serialize=False,
                unique=True,
            ),
        ),
        ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
        ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
        ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
        (
            "created_by",
            models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="%(class)s_created_by",
                to="db.user",
                verbose_name="Created By",
            ),
        ),
        (
            "updated_by",
            models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="%(class)s_updated_by",
                to="db.user",
                verbose_name="Last Modified By",
            ),
        ),
        (
            "project",
            models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="project_%(class)s",
                to="db.project",
            ),
        ),
        (
            "workspace",
            models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="workspace_%(class)s",
                to="db.workspace",
            ),
        ),
    ]

class Migration(migrations.Migration):
    dependencies = [("db", "0122_testing_library")]

    operations = [
        migrations.CreateModel(
            name="TestRun",
            fields=[
                *base_fields(),
                ("name", models.CharField(max_length=255)),
                ("description", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[("draft", "Draft"), ("active", "Active"), ("completed", "Completed")],
                        default="active",
                        max_length=20,
                    ),
                ),
                (
                    "run_type",
                    models.CharField(
                        choices=[("fixed", "Fixed"), ("live", "Live")], default="fixed", max_length=20
                    ),
                ),
                ("build", models.CharField(blank=True, default="", max_length=255)),
                ("configuration", models.JSONField(blank=True, default=dict)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "cycle",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="test_runs",
                        to="db.cycle",
                    ),
                ),
                (
                    "module",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="test_runs",
                        to="db.module",
                    ),
                ),
            ],
            options={"db_table": "test_runs", "ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="TestRunCase",
            fields=[
                *base_fields(),
                ("position", models.PositiveIntegerField()),
                (
                    "latest_status",
                    models.CharField(
                        choices=[
                            ("open", "Open"),
                            ("passed", "Passed"),
                            ("failed", "Failed"),
                            ("blocked", "Blocked"),
                            ("skipped", "Skipped"),
                        ],
                        default="open",
                        max_length=20,
                    ),
                ),
                (
                    "test_case",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="run_cases",
                        to="db.testcase",
                    ),
                ),
                (
                    "test_case_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="run_cases",
                        to="db.testcaseversion",
                    ),
                ),
                (
                    "test_run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="run_cases",
                        to="db.testrun",
                    ),
                ),
            ],
            options={"db_table": "test_run_cases", "ordering": ("position",)},
        ),
        migrations.CreateModel(
            name="TestResult",
            fields=[
                *base_fields(),
                ("sequence", models.PositiveIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("passed", "Passed"),
                            ("failed", "Failed"),
                            ("blocked", "Blocked"),
                            ("skipped", "Skipped"),
                        ],
                        max_length=20,
                    ),
                ),
                ("actual_result", models.JSONField(blank=True, default=dict)),
                ("duration_ms", models.PositiveBigIntegerField(blank=True, null=True)),
                (
                    "executed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="test_results",
                        to="db.user",
                    ),
                ),
                (
                    "run_case",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="results",
                        to="db.testruncase",
                    ),
                ),
            ],
            options={"db_table": "test_results", "ordering": ("sequence",)},
        ),
        migrations.AddConstraint(
            model_name="testruncase",
            constraint=models.UniqueConstraint(
                fields=("test_run", "test_case"), name="unique_test_case_per_run"
            ),
        ),
        migrations.AddConstraint(
            model_name="testruncase",
            constraint=models.UniqueConstraint(
                fields=("test_run", "position"), name="unique_test_run_case_position"
            ),
        ),
        migrations.AddConstraint(
            model_name="testresult",
            constraint=models.UniqueConstraint(
                fields=("run_case", "sequence"), name="unique_test_result_sequence"
            ),
        ),
    ]
