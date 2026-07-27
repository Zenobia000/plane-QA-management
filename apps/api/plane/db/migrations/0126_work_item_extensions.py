# Generated manually for CE work-item extensions on 2026-07-27.

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
    ]


def project_base_fields():
    return [
        *base_fields(),
        ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="project_%(class)s", to="db.project")),
        ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="workspace_%(class)s", to="db.workspace")),
    ]


class Migration(migrations.Migration):
    dependencies = [("db", "0125_testing_automation")]

    operations = [
        migrations.CreateModel(
            name="Initiative",
            fields=[
                *base_fields(),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("planned", "Planned"), ("in_progress", "In progress"), ("completed", "Completed"), ("cancelled", "Cancelled")], default="planned", max_length=32)),
                ("target_date", models.DateField(blank=True, null=True)),
                ("sort_order", models.FloatField(default=65535)),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="initiatives", to="db.workspace")),
            ],
            options={"db_table": "initiatives", "ordering": ("target_date", "sort_order", "created_at")},
        ),
        migrations.CreateModel(
            name="Milestone",
            fields=[
                *project_base_fields(),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("target_date", models.DateField(blank=True, null=True)),
                ("status", models.CharField(choices=[("planned", "Planned"), ("in_progress", "In progress"), ("completed", "Completed"), ("cancelled", "Cancelled")], default="planned", max_length=32)),
                ("sort_order", models.FloatField(default=65535)),
            ],
            options={"db_table": "milestones", "ordering": ("target_date", "sort_order", "created_at")},
        ),
        migrations.CreateModel(
            name="WorkItemProperty",
            fields=[
                *project_base_fields(),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("kind", models.CharField(choices=[("text", "Text"), ("number", "Number"), ("date", "Date"), ("boolean", "Boolean"), ("select", "Select"), ("multi_select", "Multi select"), ("url", "URL")], max_length=32)),
                ("is_required", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.FloatField(default=65535)),
                ("default_value", models.JSONField(blank=True, null=True)),
            ],
            options={"db_table": "work_item_properties", "ordering": ("sort_order", "created_at")},
        ),
        migrations.CreateModel(
            name="InitiativeProject",
            fields=[
                *base_fields(),
                ("initiative", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="initiative_projects", to="db.initiative")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="project_initiatives", to="db.project")),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="workspace_initiative_projects", to="db.workspace")),
            ],
            options={"db_table": "initiative_projects"},
        ),
        migrations.CreateModel(
            name="WorkItemPropertyOption",
            fields=[
                *project_base_fields(),
                ("label", models.CharField(max_length=255)),
                ("value", models.CharField(max_length=255)),
                ("sort_order", models.FloatField(default=65535)),
                ("property", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="options", to="db.workitemproperty")),
            ],
            options={"db_table": "work_item_property_options", "ordering": ("sort_order", "created_at")},
        ),
        migrations.CreateModel(
            name="WorkItemPropertyValue",
            fields=[
                *project_base_fields(),
                ("value", models.JSONField(blank=True, null=True)),
                ("issue", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="property_values", to="db.issue")),
                ("property", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="values", to="db.workitemproperty")),
            ],
            options={"db_table": "work_item_property_values"},
        ),
        migrations.AddField(
            model_name="issue",
            name="milestone",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="work_items", to="db.milestone"),
        ),
        migrations.AddConstraint(
            model_name="initiative",
            constraint=models.UniqueConstraint(condition=models.Q(("deleted_at__isnull", True)), fields=("workspace", "name"), name="initiative_unique_name_workspace_when_active"),
        ),
        migrations.AddConstraint(
            model_name="initiativeproject",
            constraint=models.UniqueConstraint(condition=models.Q(("deleted_at__isnull", True)), fields=("initiative", "project"), name="initiative_project_unique_when_active"),
        ),
        migrations.AddConstraint(
            model_name="milestone",
            constraint=models.UniqueConstraint(condition=models.Q(("deleted_at__isnull", True)), fields=("project", "name"), name="milestone_unique_name_project_when_active"),
        ),
        migrations.AddConstraint(
            model_name="workitemproperty",
            constraint=models.UniqueConstraint(condition=models.Q(("deleted_at__isnull", True)), fields=("project", "name"), name="work_item_property_unique_name_project_when_active"),
        ),
        migrations.AddConstraint(
            model_name="workitempropertyoption",
            constraint=models.UniqueConstraint(condition=models.Q(("deleted_at__isnull", True)), fields=("property", "value"), name="work_item_property_option_unique_value_when_active"),
        ),
        migrations.AddConstraint(
            model_name="workitempropertyvalue",
            constraint=models.UniqueConstraint(condition=models.Q(("deleted_at__isnull", True)), fields=("issue", "property"), name="work_item_property_value_unique_issue_property_when_active"),
        ),
    ]
