# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Soft delete the rows left alive under a soft-deleted project.

Deleting a project is supposed to sweep everything it owns, via the
`soft_delete_related_objects` task that `SoftDeleteModel.delete()` queues. Two things
stop that from being the whole story, and this command exists to reconcile the result:

- a queryset `delete()` is a bulk `update(deleted_at=...)` that never reaches the
  instance method, so nothing is ever queued. Anything removed that way -- a cleanup
  script, a bulk purge -- leaves its children behind entirely
- the task saves each child through the model, and the testing half of the schema
  refuses to be saved. Published versions are immutable and results are append-only, so
  the guard raises, the task logs and moves on, and those rows are never swept even when
  the cascade did run correctly

The second reason is why this is written as an `update()` rather than a loop over
`delete()`. Bypassing the model layer is the point: those invariants are about editing
content, and applying them to lifecycle deletion leaves the rows permanently
unreachable-but-alive. Nothing here touches a row whose project is still live.

Run with `--dry-run` first; it reports exactly what the real run would change.
"""

# Django imports
from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import OuterRef, Subquery

# Module imports
from plane.db.models import Project


class Command(BaseCommand):
    help = "Soft delete rows still alive under soft-deleted projects."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be swept without writing anything.",
        )
        parser.add_argument(
            "--workspace",
            default=None,
            help="Limit the sweep to one workspace slug. Defaults to every workspace.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        workspace = options["workspace"]

        dead = Project.all_objects.filter(deleted_at__isnull=False)
        if workspace:
            dead = dead.filter(workspace__slug=workspace)
        if not dead.exists():
            self.stdout.write("No soft-deleted projects. Nothing to sweep.")
            return

        project_ids = list(dead.values_list("id", flat=True))
        # Each row inherits the deleted_at of the project that owned it, so the sweep
        # records when the data actually became unreachable rather than when this ran.
        stamp = Project.all_objects.filter(pk=OuterRef("project_id")).values("deleted_at")[:1]

        swept = {}
        with transaction.atomic():
            for model in self._sweepable_models():
                manager = getattr(model, "all_objects", model.objects)
                orphans = manager.filter(project_id__in=project_ids, deleted_at__isnull=True)
                if dry_run:
                    count = orphans.count()
                else:
                    count = orphans.update(deleted_at=Subquery(stamp))
                if count:
                    swept[model._meta.db_table] = count

            if dry_run:
                transaction.set_rollback(True)

        self._report(swept, len(project_ids), dry_run)

    @staticmethod
    def _sweepable_models():
        """Every model that a project owns and that can be soft deleted."""
        for model in apps.get_app_config("db").get_models():
            try:
                project = model._meta.get_field("project")
                model._meta.get_field("deleted_at")
            except FieldDoesNotExist:
                continue
            # `project` also names the reverse accessor on the models a project points
            # at. Only a concrete forward FK gives us a project_id column to filter on.
            if project.many_to_one and project.concrete:
                yield model

    def _report(self, swept, project_count, dry_run):
        verb = "Would sweep" if dry_run else "Swept"
        if not swept:
            self.stdout.write(self.style.SUCCESS(f"Nothing orphaned under {project_count} deleted project(s)."))
            return

        for table, count in sorted(swept.items(), key=lambda pair: -pair[1]):
            self.stdout.write(f"  {count:>6}  {table}")
        total = sum(swept.values())
        self.stdout.write(
            self.style.SUCCESS(f"{verb} {total} row(s) across {len(swept)} table(s), under {project_count} project(s).")
        )
