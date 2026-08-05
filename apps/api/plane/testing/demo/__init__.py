# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Builds a project that demonstrates every relationship the platform models.

The ordering below is not arbitrary. Classification has to exist before anything can be
classified, the breakdown before anything can be scheduled against it, contracts before
they can be pinned by a run, and results before a defect can be born from one. Following
the sequence top to bottom is a reasonable way to learn the model.

Everything in the testing half goes through `plane.testing.services`, so the seeded data
is subject to the same four invariants as production data: immutable versions, pinned run
membership, append-only results, and defects only from failed or blocked results.

See `docs/process/plane-qa-guideline.md` B0 for the diagram this project instantiates.
"""

# Django imports
from django.db import transaction

# Module imports
from plane.db.models import Initiative, IssueView, Page, Project, State
from plane.testing.demo import (
    contracts,
    evidence,
    execution,
    frontline,
    pages,
    planning,
    saved_views,
    scaffolding,
)

# Read from the modules that create them rather than restated here. Both were duplicated
# literals until a rename in planning.py left this file purging a name nothing created,
# which broke `--force` re-seeding on the initiative's active-name uniqueness constraint.
DEMO_INITIATIVE_NAME = planning.INITIATIVE_NAME
DEMO_WORKSPACE_VIEW_NAME = saved_views.WORKSPACE_VIEW_NAME


def purge(workspace, identifier):
    """Remove a previous run of this seed, including what its deletion leaves behind.

    `Project.delete()` is a soft delete: the row stays with `deleted_at` set, and saved
    views are not swept with it. Repeated seeding therefore accumulates orphan views that
    point at projects the UI no longer shows -- nine soft-deleted DEMO projects and five
    such views existed before this was handled. Views are cleared explicitly, and against
    every project carrying the identifier rather than only the live one.

    Two more things survive because they do not belong to the project at all: the
    workspace-level initiative and the workspace-level view. Both are removed by the names
    this module owns -- never by a blanket delete, which would take other projects'
    initiatives with it.
    """
    removed = []

    # Includes soft-deleted rows, whose views would otherwise be stranded forever.
    manager = getattr(Project, "all_objects", Project.objects)
    project_ids = list(
        manager.filter(workspace=workspace, identifier=identifier).values_list("id", flat=True)
    )
    if project_ids:
        stale_views = IssueView.objects.filter(project_id__in=project_ids)
        count = stale_views.count()
        if count:
            removed.append(f"{count} saved view(s) from earlier {identifier} projects")
            stale_views.delete()

        # Pages are workspace-owned and reach a project only through `ProjectPage`, so the
        # project's cascade sweeps the join row and leaves the page itself behind -- the
        # same shape of orphan saved views used to leave. Deleted parent-first so the
        # self-referencing cascade takes the children with it.
        stale_pages = Page.objects.filter(project_pages__project_id__in=project_ids).distinct()
        count = stale_pages.count()
        if count:
            removed.append(f"{count} page(s) from earlier {identifier} projects")
            for page in stale_pages.filter(parent__isnull=True):
                page.delete()
            for page in Page.objects.filter(project_pages__project_id__in=project_ids).distinct():
                page.delete()

    projects = Project.objects.filter(workspace=workspace, identifier=identifier)
    if projects.exists():
        removed.append(f"project {identifier}")
        # Deleted one row at a time on purpose. A queryset `delete()` is a bulk
        # `update(deleted_at=...)`, which never reaches `SoftDeleteModel.delete()` and so
        # never queues the cascade that sweeps a project's cycles, work items and their
        # join rows. Earlier runs of this seed left 17 cycles and 145 work items alive
        # under projects the UI had already stopped showing.
        for project in projects:
            project.delete()

    initiatives = Initiative.objects.filter(workspace=workspace, name=DEMO_INITIATIVE_NAME)
    if initiatives.exists():
        removed.append(f"initiative {DEMO_INITIATIVE_NAME}")
        # Same reason: an initiative owns InitiativeProject rows that the bulk path strands.
        for initiative in initiatives:
            initiative.delete()

    views = IssueView.objects.filter(
        workspace=workspace, project__isnull=True, name=DEMO_WORKSPACE_VIEW_NAME
    )
    if views.exists():
        removed.append(f"workspace view {DEMO_WORKSPACE_VIEW_NAME}")
        views.delete()

    return removed


@transaction.atomic
def seed(workspace, owner, identifier):
    """Create the demo project and return the pieces a caller may want to report on."""
    project = scaffolding.create_project(workspace, owner, identifier)
    # Keyed by name, not by group. With one state per group the two were interchangeable;
    # the SDLC set puts nine states in `started`, so a group-keyed dict would silently keep
    # whichever one the queryset happened to yield last and every item would land there.
    states = {state.name: state for state in State.objects.filter(project=project)}

    # Classification first: nothing can be typed, tagged, sized or scheduled against a
    # checkpoint that does not exist yet.
    types = scaffolding.create_work_item_types(workspace, project)
    properties = scaffolding.create_properties(project)
    labels = scaffolding.create_labels(workspace, project, owner)
    points = scaffolding.create_estimate(project, workspace, owner)
    milestones = scaffolding.create_milestones(project, workspace, owner)

    initiative = planning.create_initiative(workspace, project, owner)
    modules, cycles = planning.create_schedule(workspace, project, owner)

    context = {
        "types": types, "states": states, "properties": properties, "labels": labels,
        "points": points, "milestones": milestones, "modules": modules, "cycles": cycles,
    }
    items = planning.create_hierarchy(workspace, project, owner, context)
    # After the items exist and before anything reads a burndown: the completion stamps
    # Issue.save() just wrote all point at today, which is outside both sprint windows.
    planning.settle_completion_dates(cycles, items)
    planning.create_relations(workspace, project, owner, items)
    planning.create_external_links(workspace, project, owner, items)
    planning.create_comments(workspace, project, owner, items)

    folders, cases = contracts.create_contracts(project, items)
    contracts.create_automation_links(project, cases, owner)

    runs = execution.execute(project, owner, cases, modules, cycles)
    defect = execution.close_the_loop(project, owner, runs, states)

    evidence.record_release_evidence(workspace, project, owner)
    evidence.record_ingestion(project, runs["current"][0], owner)

    # Last, because the overview reads across everything above it: the noticeboard sits on
    # the project, the field reports become work items, and both are only interesting once
    # there is a project for them to be about.
    field = frontline.create_frontline(workspace, project, owner, labels)
    # Named for what it holds. This was `folders` until the page tree arrived and reused
    # the name, which left the returned "folders" key holding pages and the test folders
    # unreachable -- a caller asking for folders got the other tree with no error anywhere.
    page_folders = pages.create_pages(workspace, project, owner)

    views = saved_views.create_views(workspace, project, owner, context)

    return {
        "project": project,
        "initiative": initiative,
        "types": types,
        "cycles": cycles,
        "items": items,
        "labels": labels,
        "properties": properties,
        "milestones": milestones,
        "folders": folders,
        "cases": cases,
        "runs": runs,
        "defect": defect,
        "views": views,
        "frontline": field,
        "pages": page_folders,
    }
