# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

from django.conf import settings
from django.db.models import F, Prefetch
from django.http import HttpResponse, HttpResponseRedirect
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from plane.app.permissions import ProjectEntityPermission
from plane.app.serializers.testing import (
    TestCaseAttachmentSerializer,
    TestCaseSerializer,
    TestCaseWriteSerializer,
    TestCaseVersionSerializer,
    TestCaseWorkItemLinkSerializer,
    TestCaseWorkItemLinkWriteSerializer,
    TestFolderSerializer,
    TestFolderWriteSerializer,
    TestLibraryCSVImportSerializer,
)
from plane.app.views.base import BaseAPIView
from plane.bgtasks.storage_metadata_task import get_asset_object_metadata
from plane.db.models import FileAsset, TestCase, TestCaseVersion, TestCaseWorkItemLink, TestFolder, TestStep, Workspace
from plane.settings.storage import S3Storage
from plane.testing import create_test_case, create_test_folder, link_test_case_to_work_item, publish_test_case_version
from plane.testing.portability import export_test_library_csv, import_test_library_csv
from plane.testing.search import export_testing_records, search_testing_records
from plane.utils.path_validator import sanitize_filename


def _case_queryset(*, slug, project_id):
    return (
        TestCase.objects.filter(
            workspace__slug=slug,
            project_id=project_id,
            archived_at__isnull=True,
        )
        .select_related("folder")
        .prefetch_related(
            Prefetch(
                "versions",
                queryset=TestCaseVersion.objects.prefetch_related(
                    Prefetch("steps", queryset=TestStep.objects.order_by("position"))
                ),
            )
        )
        .prefetch_related("work_item_links__issue__state")
        .prefetch_related("run_cases__test_run", "run_cases__test_case_version")
    )


class TestFolderListCreateEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        folders = TestFolder.objects.filter(workspace__slug=slug, project_id=project_id).order_by("sort_order", "name")
        return Response(TestFolderSerializer(folders, many=True).data)

    def post(self, request, slug, project_id):
        serializer = TestFolderWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        folder = create_test_folder(project_id=project_id, **serializer.validated_data)
        return Response(TestFolderSerializer(folder).data, status=status.HTTP_201_CREATED)


class TestFolderDetailEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id, folder_id):
        folder = TestFolder.objects.get(id=folder_id, workspace__slug=slug, project_id=project_id)
        return Response(TestFolderSerializer(folder).data)

    def patch(self, request, slug, project_id, folder_id):
        folder = TestFolder.objects.get(id=folder_id, workspace__slug=slug, project_id=project_id)
        serializer = TestFolderWriteSerializer(
            data={
                "name": request.data.get("name", folder.name),
                "parent_id": request.data.get("parent_id", folder.parent_id),
                "sort_order": request.data.get("sort_order", folder.sort_order),
            }
        )
        serializer.is_valid(raise_exception=True)
        parent_id = serializer.validated_data["parent_id"]
        parent = (
            TestFolder.objects.get(id=parent_id, workspace__slug=slug, project_id=project_id) if parent_id else None
        )
        ancestor = parent
        visited = set()
        while ancestor is not None and ancestor.id not in visited:
            if ancestor.id == folder.id:
                raise ValidationError({"parent_id": "A test folder cannot be moved below itself or its descendants."})
            visited.add(ancestor.id)
            ancestor = ancestor.parent
        folder.name = serializer.validated_data["name"]
        folder.parent = parent
        folder.sort_order = serializer.validated_data["sort_order"]
        folder.full_clean(exclude=("created_by", "updated_by"))
        folder.save(update_fields=["name", "parent", "sort_order", "updated_at", "updated_by"])
        return Response(TestFolderSerializer(folder).data)

    def delete(self, request, slug, project_id, folder_id):
        folder = TestFolder.objects.get(id=folder_id, workspace__slug=slug, project_id=project_id)
        if folder.children.exists() or folder.test_cases.filter(archived_at__isnull=True).exists():
            return Response(
                {"error": "Only an empty test folder can be deleted."},
                status=status.HTTP_409_CONFLICT,
            )
        folder.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TestCaseListCreateEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        cases = _case_queryset(slug=slug, project_id=project_id)
        folder_id = request.query_params.get("folder_id")
        if folder_id:
            cases = cases.filter(folder_id=folder_id)
        work_item_id = request.query_params.get("work_item_id")
        if work_item_id:
            cases = cases.filter(work_item_links__issue_id=work_item_id).distinct()
        search = request.query_params.get("search", "").strip()
        if search:
            cases = cases.filter(
                versions__version=F("current_version"),
                versions__title__icontains=search,
            ).distinct()
        if request.query_params.get("per_page") or request.query_params.get("cursor"):
            return self.paginate(
                request=request,
                queryset=cases,
                order_by="sequence",
                on_results=lambda items: TestCaseSerializer(items, many=True).data,
                default_per_page=50,
                max_per_page=200,
            )
        return Response(TestCaseSerializer(cases, many=True).data)

    def post(self, request, slug, project_id):
        serializer = TestCaseWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        test_case = create_test_case(project_id=project_id, **serializer.validated_data)
        test_case = _case_queryset(slug=slug, project_id=project_id).get(id=test_case.id)
        return Response(TestCaseSerializer(test_case).data, status=status.HTTP_201_CREATED)


class TestCaseDetailEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id, test_case_id):
        test_case = _case_queryset(slug=slug, project_id=project_id).get(id=test_case_id)
        return Response(TestCaseSerializer(test_case).data)

    def patch(self, request, slug, project_id, test_case_id):
        test_case = _case_queryset(slug=slug, project_id=project_id).get(id=test_case_id)
        current = test_case.versions.get(version=test_case.current_version)
        initial = {
            "title": current.title,
            "folder_id": test_case.folder_id,
            "description": current.description,
            "preconditions": current.preconditions,
            "priority": current.priority,
            "tags": current.tags,
            "steps": [{"action": step.action, "expected_result": step.expected_result} for step in current.steps.all()],
        }
        payload = {**initial, **request.data}
        serializer = TestCaseWriteSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        folder_id = serializer.validated_data.pop("folder_id", test_case.folder_id)
        if folder_id != test_case.folder_id:
            folder = TestFolder.objects.get(id=folder_id, project_id=project_id) if folder_id else None
            TestCase.objects.filter(id=test_case.id).update(folder=folder)
        publish_test_case_version(
            test_case_id=test_case.id,
            project_id=project_id,
            **serializer.validated_data,
        )
        updated = _case_queryset(slug=slug, project_id=project_id).get(id=test_case_id)
        return Response(TestCaseSerializer(updated).data)

    def delete(self, request, slug, project_id, test_case_id):
        updated = TestCase.objects.filter(
            id=test_case_id,
            workspace__slug=slug,
            project_id=project_id,
        ).update(archived_at=timezone.now())
        if not updated:
            return Response({"error": "Test case not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TestCaseVersionDetailEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id, test_case_id, version):
        item = (
            TestCaseVersion.objects.filter(
                workspace__slug=slug,
                project_id=project_id,
                test_case_id=test_case_id,
                version=version,
            )
            .prefetch_related("steps")
            .get()
        )
        return Response(TestCaseVersionSerializer(item).data)


class TestCaseAttachmentEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def _test_case(self, *, slug, project_id, test_case_id):
        return TestCase.objects.get(
            id=test_case_id,
            workspace__slug=slug,
            project_id=project_id,
        )

    def _attachment(self, *, slug, project_id, test_case_id, attachment_id):
        return FileAsset.objects.get(
            id=attachment_id,
            workspace__slug=slug,
            project_id=project_id,
            entity_type=FileAsset.EntityTypeContext.TESTING_ARTIFACT,
            entity_identifier=str(test_case_id),
            is_deleted=False,
        )

    def get(self, request, slug, project_id, test_case_id, attachment_id=None):
        self._test_case(slug=slug, project_id=project_id, test_case_id=test_case_id)
        if attachment_id:
            attachment = self._attachment(
                slug=slug,
                project_id=project_id,
                test_case_id=test_case_id,
                attachment_id=attachment_id,
            )
            if not attachment.is_uploaded:
                return Response({"error": "The attachment is not uploaded."}, status=status.HTTP_404_NOT_FOUND)
            mime_type = attachment.attributes.get("type", "")
            preview = request.query_params.get("preview") == "true" and mime_type.startswith("image/")
            storage = S3Storage(request=request)
            signed_url = storage.generate_presigned_url(
                object_name=attachment.asset.name,
                disposition="inline" if preview else "attachment",
                filename=attachment.attributes.get("name"),
                mime_type=mime_type,
            )
            return HttpResponseRedirect(signed_url)

        attachments = FileAsset.objects.filter(
            workspace__slug=slug,
            project_id=project_id,
            entity_type=FileAsset.EntityTypeContext.TESTING_ARTIFACT,
            entity_identifier=str(test_case_id),
            is_uploaded=True,
            is_deleted=False,
        )
        return Response(TestCaseAttachmentSerializer(attachments, many=True, context={"request": request}).data)

    def post(self, request, slug, project_id, test_case_id):
        test_case = self._test_case(slug=slug, project_id=project_id, test_case_id=test_case_id)
        if test_case.archived_at:
            return Response(
                {"error": "Archived test cases cannot receive attachments."}, status=status.HTTP_409_CONFLICT
            )
        name = sanitize_filename(request.data.get("name")) or "unnamed"
        mime_type = request.data.get("type")
        try:
            size = int(request.data.get("size", 0))
        except (TypeError, ValueError):
            size = 0
        if not mime_type or mime_type not in settings.ATTACHMENT_MIME_TYPES:
            return Response({"error": "Invalid file type."}, status=status.HTTP_400_BAD_REQUEST)
        if size < 1 or size > settings.FILE_SIZE_LIMIT:
            return Response(
                {"error": f"File size must be between 1 and {settings.FILE_SIZE_LIMIT} bytes."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        workspace = Workspace.objects.get(slug=slug)
        asset_key = f"{workspace.id}/{uuid.uuid4().hex}-{name}"
        attachment = FileAsset.objects.create(
            attributes={"name": name, "type": mime_type, "size": size},
            asset=asset_key,
            size=size,
            workspace=workspace,
            project_id=project_id,
            created_by=request.user,
            entity_type=FileAsset.EntityTypeContext.TESTING_ARTIFACT,
            entity_identifier=str(test_case.id),
        )
        upload_data = S3Storage(request=request).generate_presigned_post(
            object_name=asset_key,
            file_type=mime_type,
            file_size=size,
        )
        serialized_attachment = TestCaseAttachmentSerializer(attachment, context={"request": request}).data
        return Response(
            {
                "upload_data": upload_data,
                "asset_id": str(attachment.id),
                "asset_url": serialized_attachment["download_url"],
                "attachment": serialized_attachment,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, slug, project_id, test_case_id, attachment_id):
        attachment = self._attachment(
            slug=slug,
            project_id=project_id,
            test_case_id=test_case_id,
            attachment_id=attachment_id,
        )
        if not attachment.is_uploaded:
            attachment.is_uploaded = True
            attachment.save(update_fields=["is_uploaded", "updated_at"])
        if not attachment.storage_metadata:
            get_asset_object_metadata.delay(str(attachment.id))
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request, slug, project_id, test_case_id, attachment_id):
        attachment = self._attachment(
            slug=slug,
            project_id=project_id,
            test_case_id=test_case_id,
            attachment_id=attachment_id,
        )
        attachment.is_deleted = True
        attachment.deleted_at = timezone.now()
        attachment.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class TestCaseWorkItemLinkEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id, test_case_id):
        links = TestCaseWorkItemLink.objects.filter(
            workspace__slug=slug,
            project_id=project_id,
            test_case_id=test_case_id,
        ).order_by("created_at")
        return Response(TestCaseWorkItemLinkSerializer(links, many=True).data)

    def post(self, request, slug, project_id, test_case_id):
        serializer = TestCaseWorkItemLinkWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        link = link_test_case_to_work_item(
            test_case_id=test_case_id,
            project_id=project_id,
            **serializer.validated_data,
        )
        return Response(TestCaseWorkItemLinkSerializer(link).data, status=status.HTTP_201_CREATED)


class TestCaseWorkItemLinkDetailEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def delete(self, request, slug, project_id, test_case_id, issue_id):
        link = TestCaseWorkItemLink.objects.filter(
            workspace__slug=slug,
            project_id=project_id,
            test_case_id=test_case_id,
            issue_id=issue_id,
        ).first()
        if link is None:
            return Response({"error": "Test case work item link not found."}, status=status.HTTP_404_NOT_FOUND)
        link.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TestLibraryCSVEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        csv_text = export_test_library_csv(project_id=project_id)
        response = HttpResponse(csv_text, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="plane-testing-library.csv"'
        return response

    def post(self, request, slug, project_id):
        serializer = TestLibraryCSVImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = import_test_library_csv(
            project_id=project_id,
            csv_text=serializer.validated_data["csv_text"],
            created_by=request.user,
        )
        return Response(result, status=status.HTTP_201_CREATED)


class TestLibrarySearchEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        query = request.query_params.get("query", "").strip()
        scope = request.query_params.get("scope", "all").strip()
        try:
            limit = int(request.query_params.get("limit", 200))
        except (TypeError, ValueError) as exc:
            raise ValidationError({"limit": "Limit must be an integer."}) from exc
        records = search_testing_records(project_id=project_id, query=query, scope=scope, limit=limit)
        return Response({"query": query, "scope": scope, "count": len(records), "results": records})


class TestLibraryExportEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        query = request.query_params.get("query", "").strip()
        scope = request.query_params.get("scope", "all").strip()
        export_format = request.query_params.get("export_format", "csv").strip().casefold()
        records = search_testing_records(project_id=project_id, query=query, scope=scope, limit=200)
        content, content_type, filename = export_testing_records(records=records, export_format=export_format)
        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
