# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("db", "0126_work_item_extensions")]

    operations = [
        migrations.AddField(
            model_name="testcaseversion",
            name="case_type",
            field=models.CharField(
                choices=[
                    ("functional", "Functional"),
                    ("performance", "Performance"),
                    ("security", "Security"),
                    ("reliability", "Reliability"),
                    ("compliance", "Compliance"),
                ],
                default="functional",
                max_length=20,
            ),
        )
    ]
