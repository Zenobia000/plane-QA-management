# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("db", "0139_work_item_property_type")]

    operations = [
        migrations.AddField(
            model_name="issue",
            name="requirement_kind",
            # Defaults to "none": every existing row predates the field, and claiming a
            # classification nobody made would be worse than admitting there isn't one.
            # `converge_work_item_types` sets it where the old type carried the answer.
            field=models.CharField(
                choices=[
                    ("none", "Not a requirement"),
                    ("functional", "Functional"),
                    ("quality", "Quality"),
                ],
                default="none",
                max_length=20,
            ),
        )
    ]
