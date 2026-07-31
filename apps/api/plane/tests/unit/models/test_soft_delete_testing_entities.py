# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""Retiring a testing row, versus editing one.

The testing entities refuse writes to a published row. Soft deletion reaches a model through
the same `save()`, so those guards used to reject the cascade too and the rows outlived the
project that owned them -- 250 versions and 149 results on the database that prompted this.

The two halves have to stay true together: a delete must get through, and an edit must still
not. Each guarded model is checked for both.
"""

from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.utils import timezone

from plane.db.models import Project, TestCaseVersion, TestResult, TestStep
from plane.db.soft_delete import SOFT_DELETE_FIELDS, is_soft_delete_save


@pytest.fixture
def eager_tasks():
    """Run the cascade in-process; with no worker attached it would never run at all."""
    from plane.celery import app

    previous = app.conf.task_always_eager
    app.conf.task_always_eager = True
    yield
    app.conf.task_always_eager = previous


@pytest.fixture
def seeded(workspace):
    call_command("seed_testing_demo", workspace=workspace.slug, identifier="DEMO", stdout=StringIO())
    return Project.objects.get(workspace=workspace, identifier="DEMO")


@pytest.mark.unit
class TestIsSoftDeleteSave:
    """The discriminator itself, which is the whole of the exemption."""

    def test_a_save_naming_only_lifecycle_columns_is_a_delete(self):
        assert is_soft_delete_save({"update_fields": list(SOFT_DELETE_FIELDS)})
        assert is_soft_delete_save({"update_fields": ["deleted_at"]})

    def test_a_save_naming_no_fields_is_an_edit(self):
        """A full-row save rewrites content whatever the caller meant by it."""
        assert not is_soft_delete_save({})
        assert not is_soft_delete_save({"update_fields": None})
        assert not is_soft_delete_save({"update_fields": []})

    def test_a_save_smuggling_a_content_column_is_an_edit(self):
        assert not is_soft_delete_save({"update_fields": ["deleted_at", "name"]})


@pytest.mark.unit
@pytest.mark.django_db
class TestPublishedRowsStayImmutable:
    """The guards must still do the job they were written for."""

    def test_a_version_cannot_be_edited(self, seeded):
        version = TestCaseVersion.objects.filter(project=seeded).first()
        version.summary = "rewritten"
        with pytest.raises(ValidationError):
            version.save()

    def test_a_step_cannot_be_edited(self, seeded):
        step = TestStep.objects.filter(project=seeded).first()
        step.position = step.position + 100
        with pytest.raises(ValidationError):
            step.save()

    def test_a_result_cannot_be_edited(self, seeded):
        result = TestResult.objects.filter(project=seeded).first()
        result.sequence = result.sequence + 100
        with pytest.raises(ValidationError):
            result.save()


@pytest.mark.unit
@pytest.mark.django_db
class TestRetirementIsAllowed:
    def test_a_version_can_be_soft_deleted(self, seeded):
        version = TestCaseVersion.objects.filter(project=seeded).first()
        version.delete()
        assert TestCaseVersion.all_objects.get(pk=version.pk).deleted_at is not None

    def test_a_result_can_be_soft_deleted(self, seeded):
        result = TestResult.objects.filter(project=seeded).first()
        result.delete()
        assert TestResult.all_objects.get(pk=result.pk).deleted_at is not None

    def test_soft_deleting_stamps_the_audit_column(self, seeded):
        """`updated_at` is in the exemption, so retiring a row still bumps it."""
        version = TestCaseVersion.objects.filter(project=seeded).first()
        before = version.updated_at
        version.delete()
        assert TestCaseVersion.all_objects.get(pk=version.pk).updated_at > before


@pytest.mark.unit
@pytest.mark.django_db
def test_deleting_a_project_sweeps_its_testing_rows(seeded, eager_tasks):
    """The behaviour the guards were blocking, through the ordinary delete path.

    No sweep command involved: this is what should have happened all along.
    """
    assert TestCaseVersion.objects.filter(project=seeded).exists()
    assert TestResult.objects.filter(project=seeded).exists()

    seeded.delete()

    assert not TestCaseVersion.objects.filter(project=seeded).exists()
    assert not TestStep.objects.filter(project=seeded).exists()
    assert not TestResult.objects.filter(project=seeded).exists()


@pytest.mark.unit
@pytest.mark.django_db
def test_soft_delete_leaves_content_untouched(seeded):
    """The exemption must write the lifecycle columns and nothing else."""
    version = TestCaseVersion.objects.filter(project=seeded).first()
    title = version.title

    # A stale in-memory edit alongside the delete must not reach the row.
    version.title = "should not be persisted"
    version.deleted_at = timezone.now()
    version.save(update_fields=list(SOFT_DELETE_FIELDS))

    assert TestCaseVersion.all_objects.get(pk=version.pk).title == title
