# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db.models import F, Prefetch
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from django.http import HttpResponse

from plane.app.permissions import ProjectEntityPermission
from plane.app.serializers.testing import (
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
from plane.db.models import TestCase, TestCaseVersion, TestCaseWorkItemLink, TestFolder, TestStep
from plane.testing import create_test_case, create_test_folder, link_test_case_to_work_item, publish_test_case_version
from plane.testing.portability import export_test_library_csv, import_test_library_csv


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
            TestFolder.objects.get(id=parent_id, workspace__slug=slug, project_id=project_id)
            if parent_id
            else None
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
            "steps": [
                {"action": step.action, "expected_result": step.expected_result} for step in current.steps.all()
            ],
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
