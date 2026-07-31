# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("db", "0137_intake_ingest")]

    operations = [
        migrations.AddField(
            model_name="project",
            name="is_epic_enabled",
            # True so existing projects keep the epics surface they already had. See the
            # model field's comment for why this departs from upstream EE's opt-in default.
            field=models.BooleanField(default=True),
        )
    ]
