# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Collapse hand-made work item types back onto the four the product ships.

`IssueType` is workspace-scoped, so two projects in one workspace draw from one pool.
One project here was seeded with Epic / Feature / Story / Task and another had a parallel
vocabulary typed in by hand -- Work Group, Scenario, Requirement, NFR, Work Package --
sitting at the same levels and meaning the same things. The result is two names for every
tier and, at level 2, two names that differ only by whether the requirement is functional
or a quality attribute.

That last pair is the one worth understanding, because it is not a naming accident. `type`
already carries breadth through `level`. Using it to carry requirement *nature* as well
makes the number of types the product of the two axes: this workspace grew a second level-0
type and a second level-2 type exactly that way, and a Feature-level quality requirement
would have forced a third. Nature moves to `Issue.requirement_kind`, and the axes stop
multiplying.

The target is the vocabulary the seed commands create, not the one with the most rows.
A hand-made vocabulary is by definition what a new project does *not* get, so converging
the other way would leave every future project needing the same repair.

Never merges across workspaces, and never deletes a type that still has work items on it.
"""

# Django imports
from django.core.management.base import BaseCommand
from django.db import transaction

# Module imports
from plane.db.models import Issue, IssueType, ProjectIssueType

# old name -> (canonical name, level, is_epic, requirement_kind)
MERGES = {
    "Work Group": ("Epic", 0, True, "none"),
    "Scenario": ("Epic", 0, True, "none"),
    "Requirement": ("Story", 2, False, "functional"),
    "NFR": ("Story", 2, False, "quality"),
    "Work Package": ("Task", 3, False, "none"),
}

# Canonical types that keep their name but whose rows still need a kind.
#
# Only ever applied to rows still holding the default. A merge above may already have set
# `quality` on rows that now live under this same type -- an NFR merged into Story is still
# a quality requirement -- and stamping the whole type would erase that. It did, once:
# the first run of this command wiped 106 `quality` markers a moment after setting them,
# because this pass ran second and did not exclude rows a merge had just classified.
KIND_ONLY = {"Story": "functional"}

CANONICAL = {
    "Epic": (0, True),
    "Feature": (1, False),
    "Story": (2, False),
    "Task": (3, False),
    "Bug": (2, False),
}


class Command(BaseCommand):
    help = "Merge hand-made work item types into the shipped four and stamp requirement_kind."

    def add_arguments(self, parser):
        parser.add_argument("--workspace", required=True, help="workspace slug")
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the changes. Without it the command reports and changes nothing.",
        )

    def handle(self, *args, **options):
        slug = options["workspace"]
        apply_changes = options["apply"]

        types = {t.name: t for t in IssueType.objects.filter(workspace__slug=slug)}
        if not types:
            self.stdout.write(self.style.ERROR(f"No work item types in workspace {slug!r}."))
            return

        planned = []
        problems = []

        # 1. merges
        for old_name, (new_name, level, is_epic, kind) in MERGES.items():
            old = types.get(old_name)
            if old is None:
                continue
            rows = Issue.objects.filter(type=old)
            count = rows.count()
            target = types.get(new_name)
            if target is None:
                # Nothing to merge into, so the type is already alone in its slot and only
                # wears the wrong name. Renaming touches no work items at all, where a
                # merge would rewrite every one of them to say the same thing.
                planned.append(("rename", old_name, new_name, count, kind))
                continue
            planned.append(("merge", old_name, new_name, count, kind))

        # 2. kind-only stamps
        for name, kind in KIND_ONLY.items():
            t = types.get(name)
            if t is None:
                continue
            count = Issue.objects.filter(type=t, requirement_kind="none").count()
            if count:
                planned.append(("stamp", name, name, count, kind))

        # 3. level / is_epic corrections on the canonical types
        for name, (level, is_epic) in CANONICAL.items():
            t = types.get(name)
            if t is None:
                continue
            if t.level != level or t.is_epic != is_epic:
                planned.append(("fix", name, f"level={level} is_epic={is_epic}", 0, ""))

        # 4. deletions -- only types that are both non-canonical and empty
        for name, t in types.items():
            if name in CANONICAL or name in MERGES:
                continue
            count = Issue.objects.filter(type=t).count()
            if count == 0:
                planned.append(("delete", name, "-", 0, ""))
            else:
                problems.append(f"{name!r} is unknown to this command and still holds {count} work items; left alone.")

        self._report(slug, planned, problems)

        if not apply_changes:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Dry run. Nothing was written. Re-run with --apply."))
            return

        with transaction.atomic():
            moved = self._apply(slug, types)
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Applied. {moved} work item(s) retyped."))

    def _report(self, slug, planned, problems):
        self.stdout.write(f"workspace: {slug}")
        self.stdout.write("")
        if not planned:
            self.stdout.write("Nothing to converge.")
        for kind_of_change, a, b, count, kind in planned:
            if kind_of_change == "merge":
                suffix = f"  kind={kind}" if kind != "none" else ""
                self.stdout.write(f"  MERGE   {a:<22} -> {b:<10} {count:>4} work items{suffix}")
            elif kind_of_change == "rename":
                suffix = f"  kind={kind}" if kind != "none" else ""
                self.stdout.write(f"  RENAME  {a:<22} -> {b:<10} {count:>4} work items keep type{suffix}")
            elif kind_of_change == "stamp":
                self.stdout.write(f"  STAMP   {a:<22} -> kind={kind:<10} {count:>4} work items")
            elif kind_of_change == "fix":
                self.stdout.write(f"  FIX     {a:<22} -> {b}")
            elif kind_of_change == "delete":
                self.stdout.write(f"  DELETE  {a:<22} (unused)")
        if problems:
            self.stdout.write("")
            for line in problems:
                self.stdout.write(self.style.WARNING(f"  ! {line}"))

    def _apply(self, slug, types):
        moved = 0

        for old_name, (new_name, level, is_epic, kind) in MERGES.items():
            old = types.get(old_name)
            if old is None:
                continue
            target = types.get(new_name)
            if target is None:
                # Rename in place. The rows keep their type row and only gain the kind.
                if kind != "none":
                    Issue.objects.filter(type=old).update(requirement_kind=kind)
                old.name = new_name
                old.level = level
                old.is_epic = is_epic
                old.save(update_fields=["name", "level", "is_epic"])
                types[new_name] = old
                del types[old_name]
                continue
            moved += Issue.objects.filter(type=old).update(type=target, requirement_kind=kind)
            # The per-project enablement row points at the retired type. Drop it rather than
            # repoint it: the target type may already be enabled on the same project, and the
            # table has a uniqueness constraint on the pair.
            ProjectIssueType.objects.filter(issue_type=old).delete()
            old.delete()

        for name, kind in KIND_ONLY.items():
            t = types.get(name)
            if t is None:
                continue
            Issue.objects.filter(type=t, requirement_kind="none").update(requirement_kind=kind)

        for name, (level, is_epic) in CANONICAL.items():
            t = types.get(name)
            if t is None:
                continue
            if t.level != level or t.is_epic != is_epic:
                t.level = level
                t.is_epic = is_epic
                t.save(update_fields=["level", "is_epic"])

        for name, t in list(types.items()):
            if name in CANONICAL or name in MERGES:
                continue
            if Issue.objects.filter(type=t).count() == 0:
                ProjectIssueType.objects.filter(issue_type=t).delete()
                t.delete()

        return moved
