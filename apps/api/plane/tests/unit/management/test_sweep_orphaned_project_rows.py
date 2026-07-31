# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""The reconciliation pass for children a project deletion failed to take with it.

Two paths leave rows alive under a dead project: a bulk queryset delete never queues the
cascade at all, and the cascade that does run cannot save the testing entities, whose
immutability guards reject any write. This command has to clear both, which is why it
writes through `update()` instead of the model layer.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from plane.db.models import Cycle, Issue, Project


@pytest.fixture
def dead_project(workspace):
    """A project soft-deleted the way that skips the cascade entirely."""
    call_command("seed_testing_demo", workspace=workspace.slug, identifier="DEMO", stdout=StringIO())
    project = Project.objects.get(workspace=workspace, identifier="DEMO")
    # Bulk update, exactly as a queryset delete() would: no cascade is queued.
    Project.all_objects.filter(pk=project.pk).update(deleted_at=timezone.now())
    return project


def _sweep(**kwargs):
    out = StringIO()
    call_command("sweep_orphaned_project_rows", stdout=out, **kwargs)
    return out.getvalue()


@pytest.mark.unit
@pytest.mark.django_db
class TestSweep:
    def test_dry_run_reports_without_writing(self, dead_project):
        before = Cycle.objects.filter(project=dead_project).count()
        assert before, "the seed should have left cycles behind"

        output = _sweep(dry_run=True)

        assert "Would sweep" in output
        assert Cycle.objects.filter(project=dead_project).count() == before

    def test_sweep_clears_the_orphans(self, dead_project):
        _sweep()

        assert not Cycle.objects.filter(project=dead_project).exists()
        assert not Issue.issue_objects.filter(project=dead_project).exists()

    def test_sweep_clears_rows_the_cascade_cannot_save(self, dead_project):
        """Published versions and results reject a model save, so only update() reaches them."""
        from plane.db.models import TestCaseVersion, TestResult

        assert TestCaseVersion.objects.filter(project=dead_project).exists()

        _sweep()

        assert not TestCaseVersion.objects.filter(project=dead_project).exists()
        assert not TestResult.objects.filter(project=dead_project).exists()

    def test_rows_inherit_the_projects_deletion_time(self, dead_project):
        _sweep()

        project = Project.all_objects.get(pk=dead_project.pk)
        cycle = Cycle.all_objects.filter(project=dead_project).first()
        assert cycle.deleted_at == project.deleted_at

    def test_live_projects_are_untouched(self, workspace, dead_project):
        """The boundary the sweep turns on. Built by hand rather than seeded, because the
        seed owns a workspace-scoped initiative and so can only run once per workspace."""
        live = Project.objects.create(
            workspace=workspace,
            name="Live",
            identifier="LIVE",
            created_by=workspace.owner,
        )
        cycle = Cycle.objects.create(
            workspace=workspace, project=live, name="Sprint", owned_by=workspace.owner
        )

        _sweep()

        cycle.refresh_from_db()
        assert cycle.deleted_at is None

    def test_sweeping_twice_is_a_no_op(self, dead_project):
        _sweep()
        assert "Nothing orphaned" in _sweep()
