# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
from typing import Any

# Django imports
from django.core.management.base import BaseCommand, CommandError

# Module imports
from plane.db.models import Project, User, Workspace
from plane.testing import demo


class Command(BaseCommand):
    help = (
        "Seed a traceability demo modelled on a shop-floor quality platform. Builds every "
        "relationship the platform models -- the work breakdown, the requirement-nature "
        "property, three independent scheduling cross-sections, labels, estimates, peer "
        "relations, acceptance contracts, two sprints of execution, the defect loop, CI "
        "mapping, release evidence and saved views. See docs/process/plane-qa-guideline.md."
    )

    def add_arguments(self, parser):
        parser.add_argument("--workspace", required=True, help="Workspace slug to seed into")
        parser.add_argument("--identifier", default="DEMO", help="Project identifier (default: DEMO)")
        parser.add_argument("--owner", default=None, help="Email of the seeding user; defaults to the workspace owner")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete a previous run of this seed before rebuilding, including the "
            "workspace-level initiative and view it owns",
        )

    def handle(self, *args: Any, **options: Any) -> str | None:
        workspace = self._resolve_workspace(options["workspace"])
        owner = self._resolve_owner(workspace, options["owner"])
        identifier = options["identifier"].upper()

        if Project.objects.filter(workspace=workspace, identifier=identifier).exists():
            if not options["force"]:
                raise CommandError(
                    f"Project '{identifier}' already exists in '{workspace.slug}'. "
                    "Re-run with --force to replace it; every work item, test case, run and "
                    "result it holds will be deleted, along with the workspace-level "
                    "initiative and view this seed owns."
                )
            for removed in demo.purge(workspace, identifier):
                self.stdout.write(self.style.WARNING(f"Removed {removed}"))

        result = demo.seed(workspace, owner, identifier)
        self._report(workspace, result)
        return None

    def _resolve_workspace(self, slug):
        try:
            return Workspace.objects.get(slug=slug)
        except Workspace.DoesNotExist:
            raise CommandError(f"Workspace '{slug}' does not exist.")

    def _resolve_owner(self, workspace, email):
        if email:
            try:
                return User.objects.get(email=email)
            except User.DoesNotExist:
                raise CommandError(f"User '{email}' does not exist.")
        owner = workspace.owner
        if owner is None:
            raise CommandError("The workspace has no owner; pass --owner explicitly.")
        return owner

    @staticmethod
    def _breakdown(items):
        """Counted from what was built, not restated from the design.

        The previous version of this line hard-coded eleven stories against ten that
        actually exist -- a one-word drift in a summary nobody re-checks, which is the same
        failure mode the planning documents keep hitting.
        """
        counts: dict[str, int] = {}
        for issue in items.values():
            name = issue.type.name if issue.type else "untyped"
            counts[name] = counts.get(name, 0) + 1
        plurals = (("Epic", "epics"), ("Feature", "features"), ("Story", "stories"))
        return " / ".join(f"{counts[name]} {plural}" for name, plural in plurals if name in counts)

    def _report(self, workspace, result):
        project = result["project"]
        base = f"/{workspace.slug}/projects/{project.id}/testing"
        write = self.stdout.write

        write(self.style.SUCCESS(f"Seeded {project.identifier} ({project.id})"))
        write("")
        write("  Classification")
        write("    types        Epic / Feature / Story")
        write(f"    properties   {', '.join(result['properties'])}")
        write(f"    labels       {', '.join(result['labels'])}")
        write("    estimate     Fibonacci, on stories only")
        write("")
        write("  Breakdown and schedule")
        write(f"    initiative   {result['initiative'].name} -> 1 project")
        write(f"    items        {self._breakdown(result['items'])}")
        write(f"    milestones   {', '.join(result['milestones'])}")
        write("    sprints      2026-07B delivered, 2026-08A in flight, one story carried over")
        write("    relations    2 blocked_by, 2 relates_to")
        write("")
        write("  Verification and evidence")
        write(f"    contracts    {len(result['cases'])} across functional, performance, reliability, security")
        write("    runs         2, each bound to its cycle")
        write("    automation   4 contracts mapped to CI by external_id, 1 ingestion receipt")
        write(
            f"    defect loop  {project.identifier}-{result['defect'].sequence_id} "
            "raised from a failure, retest appended beside it"
        )
        write("    release      5 evidence records for what cannot be tested before shipping")
        write("")
        field = result["frontline"]
        write("  Field and announcements")
        write(f"    grouped by   {field['dimension'].name} ({len(field['dimension'].options.all())} accounts)")
        write(f"    intake       {len(field['reports'])} reports, waiting / scheduled / declined all represented")
        write(f"    noticeboard  {len(field['announcements'])} posts, filed under project labels")
        write("")
        write(f"  Saved views    {len(result['views'])} ({len(result['views']) - 1} project, 1 workspace)")
        write("")
        write("What to look at, and what it teaches:")
        write("  a story's parent, sprint, module, milestone, kind and labels are six independent facts")
        write("  coverage rolls up, so features and epics report the contracts beneath them")
        write("  a scheduled story with no contract blocks the gate, and so does a failing SLO")
        write("  the closed sprint keeps the contract version it pinned, though the library moved on")
        write("  views filter the breakdown and the schedule -- never coverage, which is a separate query")
        write("  the overview groups field reports by a property the project chose, not one the code names")
        write("")
        write(f"  project   /{workspace.slug}/projects/{project.id}/overview")
        write(f"  overview  {base}/overview")
        write(f"  cases     {base}/cases")
        write(f"  runs      {base}/runs")
