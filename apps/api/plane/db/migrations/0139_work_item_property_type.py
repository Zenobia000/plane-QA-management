# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("db", "0138_project_is_epic_enabled")]

    operations = [
        migrations.AddField(
            model_name="workitemproperty",
            name="type",
            # Null means "every type", which is what every existing row means.
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="work_item_properties",
                to="db.issuetype",
            ),
        ),
        # The old constraint spanned every property in the project. It has to be dropped
        # before the narrowed pair goes on, or two types could never share a property name.
        migrations.RemoveConstraint(
            model_name="workitemproperty",
            name="work_item_property_unique_name_project_when_active",
        ),
        migrations.AddConstraint(
            model_name="workitemproperty",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True), ("type__isnull", True)),
                fields=("project", "name"),
                name="work_item_property_unique_name_project_when_active",
            ),
        ),
        migrations.AddConstraint(
            model_name="workitemproperty",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True), ("type__isnull", False)),
                fields=("project", "type", "name"),
                name="work_item_property_unique_name_project_type_when_active",
            ),
        ),
    ]
