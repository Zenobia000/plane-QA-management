# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""Turn the scheduling and view axes on for projects created from here on.

`AlterField` on a default is migration state only -- Django holds `default` in Python and
never writes a database default for it -- so this touches no rows and no existing project
changes behaviour. That is deliberate: a project whose team switched cycles off did so on
purpose, and a data migration flipping it back would overrule them.

Deliberately narrow. Reversing upstream's 0105 for all three fields at once would be the
same edit, but stating each separately keeps the diff readable against 0105 when a future
upstream rebase touches the same fields.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("db", "0129_merge_upstream_assignees")]

    operations = [
        migrations.AlterField(
            model_name="project",
            name="cycle_view",
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name="project",
            name="module_view",
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name="project",
            name="issue_views_view",
            field=models.BooleanField(default=True),
        ),
    ]
