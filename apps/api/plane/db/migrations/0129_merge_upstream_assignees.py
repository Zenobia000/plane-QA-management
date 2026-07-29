# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""Rejoin the migration graph after taking an upstream migration.

This fork's testing domain claimed 0122-0128, so the Django 5.2 upgrade's
0122_alter_draftissue_assignees_... arrives numbered against 0121 and leaves the
`db` app with two leaves, which `migrate` refuses to plan. Upstream's file is
kept byte-identical rather than renumbered: the numbering has diverged
permanently, so every future upstream migration lands the same way, and a merge
is the repeatable answer that does not rewrite history we want to keep
cherry-pickable.

No operations: both branches touch disjoint models, and nothing in 0122-0128
alters issue.assignees.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0122_alter_draftissue_assignees_alter_issue_assignees_and_more"),
        ("db", "0128_release_evidence"),
    ]

    operations = []
