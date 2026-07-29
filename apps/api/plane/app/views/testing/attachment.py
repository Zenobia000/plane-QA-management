# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import uuid

from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ProjectEntityPermission
from plane.app.views.base import BaseAPIView
from plane.db.models import FileAsset, TestResult, Workspace
from plane.settings.storage import S3Storage
from plane.utils.path_validator import sanitize_filename


def _serialize(asset, *, asset_url=None):
    return {
        "id": str(asset.id),
        "name": asset.attributes.get("name", ""),
        "type": asset.attributes.get("type", ""),
        "size": asset.size,
        "asset_url": asset_url,
        "created_at": asset.created_at,
    }


class TestResultAttachmentEndpoint(BaseAPIView):
    """Evidence attached to an execution result.

    CI uploads could always carry artifacts while a person recording the same
    failure by hand could not, so a screenshot never reached the developer who
    had to reproduce it. Results stay append-only: an attachment is added to the
    result it documents and removed by soft-delete, never by rewriting history.
    """

    permission_classes = [ProjectEntityPermission]

    def _result(self, project_id, run_id, run_case_id, result_id):
        return TestResult.objects.get(
            id=result_id,
            run_case_id=run_case_id,
            run_case__test_run_id=run_id,
            project_id=project_id,
        )

    def _asset(self, *, slug, project_id, result_id, pk):
        return FileAsset.objects.get(
            id=pk,
            workspace__slug=slug,
            project_id=project_id,
            entity_type=FileAsset.EntityTypeContext.TESTING_ARTIFACT,
            entity_identifier=str(result_id),
            is_deleted=False,
        )

    def get(self, request, slug, project_id, test_run_id, run_case_id, result_id, pk=None):
        result = self._result(project_id, test_run_id, run_case_id, result_id)
        if pk:
            asset = self._asset(slug=slug, project_id=project_id, result_id=result.id, pk=pk)
            if not asset.is_uploaded:
                return Response({"error": "The attachment is not uploaded."}, status=status.HTTP_404_NOT_FOUND)
            file_type = asset.attributes.get("type", "")
            signed_url = S3Storage(request=request).generate_presigned_url(
                object_name=asset.asset.name,
                disposition="inline" if file_type.startswith("image/") else "attachment",
                filename=asset.attributes.get("name"),
                mime_type=file_type,
            )
            return HttpResponseRedirect(signed_url)

        assets = FileAsset.objects.filter(
            workspace__slug=slug,
            project_id=project_id,
            entity_type=FileAsset.EntityTypeContext.TESTING_ARTIFACT,
            entity_identifier=str(result.id),
            is_uploaded=True,
            is_deleted=False,
        )
        return Response([_serialize(asset, asset_url=f"{request.path}{asset.id}/") for asset in assets])

    def post(self, request, slug, project_id, test_run_id, run_case_id, result_id):
        result = self._result(project_id, test_run_id, run_case_id, result_id)
        name = sanitize_filename(request.data.get("name")) or "unnamed"
        file_type = request.data.get("type")
        size = int(request.data.get("size", settings.FILE_SIZE_LIMIT))

        if not file_type or file_type not in settings.ATTACHMENT_MIME_TYPES:
            return Response({"error": "Invalid file type."}, status=status.HTTP_400_BAD_REQUEST)

        workspace = Workspace.objects.get(slug=slug)
        asset_key = f"{workspace.id}/{uuid.uuid4().hex}-{name}"
        size_limit = min(size, settings.FILE_SIZE_LIMIT)

        asset = FileAsset.objects.create(
            attributes={"name": name, "type": file_type, "size": size_limit},
            asset=asset_key,
            size=size_limit,
            workspace_id=workspace.id,
            project_id=project_id,
            created_by=request.user,
            entity_type=FileAsset.EntityTypeContext.TESTING_ARTIFACT,
            entity_identifier=str(result.id),
        )
        storage = S3Storage(request=request)
        presigned_url = storage.generate_presigned_post(
            object_name=asset_key, file_type=file_type, file_size=size_limit
        )
        return Response(
            {
                "upload_data": presigned_url,
                "asset_id": str(asset.id),
                "attachment": _serialize(asset, asset_url=f"{request.path}{asset.id}/"),
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, slug, project_id, test_run_id, run_case_id, result_id, pk):
        """Marks the upload complete once the object actually reached storage."""
        result = self._result(project_id, test_run_id, run_case_id, result_id)
        asset = self._asset(slug=slug, project_id=project_id, result_id=result.id, pk=pk)
        asset.is_uploaded = True
        asset.save(update_fields=["is_uploaded", "updated_at"])
        return Response(_serialize(asset, asset_url=request.path), status=status.HTTP_200_OK)

    def delete(self, request, slug, project_id, test_run_id, run_case_id, result_id, pk):
        result = self._result(project_id, test_run_id, run_case_id, result_id)
        asset = self._asset(slug=slug, project_id=project_id, result_id=result.id, pk=pk)
        asset.is_deleted = True
        asset.deleted_at = timezone.now()
        asset.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
