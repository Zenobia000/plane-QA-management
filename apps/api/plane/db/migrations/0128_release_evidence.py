# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("db", "0127_testing_case_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReleaseEvidence",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                ("id", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("slo", "Service level objective"),
                            ("scan", "Security or compliance scan"),
                            ("review", "Review or sign-off"),
                            ("other", "Other"),
                        ],
                        max_length=20,
                    ),
                ),
                ("key", models.CharField(max_length=120)),
                ("name", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[("passing", "Passing"), ("failing", "Failing"), ("pending", "Pending")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("detail", models.CharField(blank=True, default="", max_length=500)),
                ("source_url", models.URLField(blank=True, default="", max_length=800)),
                ("recorded_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by", to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="project_%(class)s",
                        to="db.project",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by", to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="workspace_%(class)s",
                        to="db.workspace",
                    ),
                ),
            ],
            options={
                "db_table": "test_release_evidence",
                "ordering": ("kind", "name"),
            },
        ),
        migrations.AddConstraint(
            model_name="releaseevidence",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("project", "key"),
                name="unique_active_release_evidence_key",
            ),
        ),
    ]
