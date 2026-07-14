# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from django.conf import settings

from plane.bgtasks.testing_artifact_task import process_testing_artifacts
from plane.db.models import FileAsset, Project, TestAutomationIngestion
from plane.testing import ingest_automation_results


def test_artifact_task_is_registered_for_celery_workers():
    assert "plane.bgtasks.testing_artifact_task" in settings.CELERY_IMPORTS


@pytest.mark.django_db
def test_artifact_task_links_only_uploaded_assets_in_ingestion_project(workspace, create_user):
    project = Project.objects.create(name="Artifacts", identifier="ART", workspace=workspace, created_by=create_user)
    other = Project.objects.create(name="Other", identifier="OTH", workspace=workspace, created_by=create_user)
    ingestion, _ = ingest_automation_results(
        project_id=project.id,
        idempotency_key="artifact-test",
        source="ci",
        name="Artifact run",
        results=[{"external_id": "one", "status": "passed"}],
        created_by=create_user,
    )
    valid = FileAsset.objects.create(
        asset="uploads/result.xml",
        workspace=workspace,
        project=project,
        user=create_user,
        is_uploaded=True,
    )
    foreign = FileAsset.objects.create(
        asset="uploads/foreign.xml",
        workspace=workspace,
        project=other,
        user=create_user,
        is_uploaded=True,
    )

    result = process_testing_artifacts(str(ingestion.id), [str(valid.id), str(foreign.id)])

    valid.refresh_from_db()
    foreign.refresh_from_db()
    ingestion = TestAutomationIngestion.objects.get(id=ingestion.id)
    assert result == {"linked": 1, "requested": 2}
    assert valid.entity_type == FileAsset.EntityTypeContext.TESTING_ARTIFACT
    assert valid.entity_identifier == str(ingestion.id)
    assert foreign.entity_type is None
    assert ingestion.diagnostics[-1] == {"code": "artifact_unavailable", "artifact_id": str(foreign.id)}
