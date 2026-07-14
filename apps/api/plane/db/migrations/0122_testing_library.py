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
    dependencies = [("db", "0121_alter_estimate_type")]

    operations = [
        migrations.CreateModel(
            name="TestFolder",
            fields=[
                *base_fields(),
                ("name", models.CharField(max_length=255)),
                ("sort_order", models.FloatField(default=65535)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="children",
                        to="db.testfolder",
                    ),
                ),
            ],
            options={"db_table": "test_folders", "ordering": ("sort_order", "name")},
        ),
        migrations.CreateModel(
            name="TestCase",
            fields=[
                *base_fields(),
                ("sequence", models.PositiveBigIntegerField()),
                ("current_version", models.PositiveIntegerField(default=1)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                (
                    "folder",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="test_cases",
                        to="db.testfolder",
                    ),
                ),
            ],
            options={"db_table": "test_cases", "ordering": ("sequence",)},
        ),
        migrations.CreateModel(
            name="TestCaseVersion",
            fields=[
                *base_fields(),
                ("version", models.PositiveIntegerField()),
                ("title", models.CharField(max_length=500)),
                ("description", models.JSONField(blank=True, default=dict)),
                ("preconditions", models.JSONField(blank=True, default=dict)),
                (
                    "priority",
                    models.CharField(
                        choices=[
                            ("urgent", "Urgent"),
                            ("high", "High"),
                            ("medium", "Medium"),
                            ("low", "Low"),
                            ("none", "None"),
                        ],
                        default="none",
                        max_length=20,
                    ),
                ),
                ("tags", models.JSONField(blank=True, default=list)),
                (
                    "test_case",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="versions",
                        to="db.testcase",
                    ),
                ),
            ],
            options={"db_table": "test_case_versions", "ordering": ("-version",)},
        ),
        migrations.CreateModel(
            name="TestStep",
            fields=[
                *base_fields(),
                ("position", models.PositiveIntegerField()),
                ("action", models.JSONField(default=dict)),
                ("expected_result", models.JSONField(blank=True, default=dict)),
                (
                    "test_case_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="steps",
                        to="db.testcaseversion",
                    ),
                ),
            ],
            options={"db_table": "test_steps", "ordering": ("position",)},
        ),
        migrations.CreateModel(
            name="TestCaseWorkItemLink",
            fields=[
                *base_fields(),
                (
                    "issue",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="test_case_links",
                        to="db.issue",
                    ),
                ),
                (
                    "test_case",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="work_item_links",
                        to="db.testcase",
                    ),
                ),
            ],
            options={"db_table": "test_case_work_item_links"},
        ),
        migrations.AddConstraint(
            model_name="testfolder",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("project", "parent", "name"),
                name="unique_active_test_folder_name",
            ),
        ),
        migrations.AddConstraint(
            model_name="testcase",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("project", "sequence"),
                name="unique_active_test_case_sequence",
            ),
        ),
        migrations.AddConstraint(
            model_name="testcaseversion",
            constraint=models.UniqueConstraint(
                fields=("test_case", "version"), name="unique_test_case_version"
            ),
        ),
        migrations.AddConstraint(
            model_name="teststep",
            constraint=models.UniqueConstraint(
                fields=("test_case_version", "position"), name="unique_test_step_position"
            ),
        ),
        migrations.AddConstraint(
            model_name="testcaseworkitemlink",
            constraint=models.UniqueConstraint(
                fields=("test_case", "issue"), name="unique_test_case_work_item_link"
            ),
        ),
    ]
