# Generated manually for the Plane native Testing domain on 2026-07-14.

import django.db.models.deletion
import uuid
from django.db import migrations, models


def base_fields():
    return [
        ("id", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
        ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
        ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
        ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
        ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(class)s_created_by", to="db.user", verbose_name="Created By")),
        ("updated_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(class)s_updated_by", to="db.user", verbose_name="Last Modified By")),
        ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="project_%(class)s", to="db.project")),
        ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="workspace_%(class)s", to="db.workspace")),
    ]


class Migration(migrations.Migration):
    dependencies = [("db", "0124_testing_defects")]
    operations = [
        migrations.CreateModel(
            name="TestCaseAutomationLink",
            fields=[
                *base_fields(),
                ("source", models.CharField(max_length=100)),
                ("external_id", models.CharField(max_length=500)),
                ("test_case", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="automation_links", to="db.testcase")),
            ],
            options={"db_table": "test_case_automation_links"},
        ),
        migrations.CreateModel(
            name="TestAutomationIngestion",
            fields=[
                *base_fields(),
                ("source", models.CharField(max_length=100)),
                ("idempotency_key", models.CharField(max_length=255)),
                ("payload_hash", models.CharField(max_length=64)),
                ("diagnostics", models.JSONField(blank=True, default=list)),
                ("test_run", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="automation_ingestion", to="db.testrun")),
            ],
            options={"db_table": "test_automation_ingestions"},
        ),
        migrations.AddConstraint(
            model_name="testcaseautomationlink",
            constraint=models.UniqueConstraint(fields=("project", "source", "external_id"), name="unique_test_case_automation_identity"),
        ),
        migrations.AddConstraint(
            model_name="testautomationingestion",
            constraint=models.UniqueConstraint(fields=("project", "idempotency_key"), name="unique_test_automation_idempotency_key"),
        ),
    ]
