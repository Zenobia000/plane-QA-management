# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from celery import shared_task

from plane.db.models import FileAsset, TestAutomationIngestion


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def process_testing_artifacts(ingestion_id, artifact_ids):
    ingestion = TestAutomationIngestion.objects.get(id=ingestion_id)
    assets = {
        str(item.id): item
        for item in FileAsset.objects.filter(
            id__in=artifact_ids,
            workspace=ingestion.workspace,
            project=ingestion.project,
            is_uploaded=True,
            is_deleted=False,
        )
    }
    diagnostics = list(ingestion.diagnostics)
    for asset_id in artifact_ids:
        asset = assets.get(str(asset_id))
        if not asset:
            diagnostics.append({"code": "artifact_unavailable", "artifact_id": str(asset_id)})
            continue
        asset.entity_type = FileAsset.EntityTypeContext.TESTING_ARTIFACT
        asset.entity_identifier = str(ingestion.id)
        asset.save(update_fields=["entity_type", "entity_identifier", "updated_at"])
    if diagnostics != ingestion.diagnostics:
        ingestion.diagnostics = diagnostics
        ingestion.save(update_fields=["diagnostics", "updated_at"])
    return {"linked": len(assets), "requested": len(artifact_ids)}
