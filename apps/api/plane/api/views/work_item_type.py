# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.response import Response

from plane.api.serializers.work_item_type import ProjectWorkItemTypeSerializer, WorkItemTypeSerializer
from plane.app.permissions import ProjectEntityPermission, WorkSpaceAdminPermission
from plane.db.models import Issue, IssueType, ProjectIssueType, Workspace

from .base import BaseAPIView


class WorkItemTypeListCreateAPIEndpoint(BaseAPIView):
    """List or create workspace-wide work-item type definitions."""

    permission_classes = [WorkSpaceAdminPermission]

    def get_queryset(self):
        return IssueType.objects.filter(workspace__slug=self.kwargs["slug"], deleted_at__isnull=True).order_by("level", "name")

    def get(self, request, slug):
        return self.paginate(
            request=request,
            queryset=self.get_queryset(),
            on_results=lambda types: WorkItemTypeSerializer(types, many=True, fields=self.fields, expand=self.expand).data,
        )

    @transaction.atomic
    def post(self, request, slug):
        workspace = Workspace.objects.get(slug=slug, deleted_at__isnull=True)
        serializer = WorkItemTypeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if IssueType.objects.filter(workspace=workspace, name__iexact=serializer.validated_data["name"], deleted_at__isnull=True).exists():
            return Response({"error": "A work item type with this name already exists."}, status=status.HTTP_409_CONFLICT)
        work_item_type = serializer.save(workspace=workspace)
        return Response(WorkItemTypeSerializer(work_item_type).data, status=status.HTTP_201_CREATED)


class WorkItemTypeDetailAPIEndpoint(BaseAPIView):
    """Update or remove a workspace-wide work-item type definition."""

    permission_classes = [WorkSpaceAdminPermission]

    def get_object(self):
        return IssueType.objects.get(
            pk=self.kwargs["type_id"], workspace__slug=self.kwargs["slug"], deleted_at__isnull=True
        )

    def get(self, request, slug, type_id):
        return Response(WorkItemTypeSerializer(self.get_object(), fields=self.fields, expand=self.expand).data)

    @transaction.atomic
    def patch(self, request, slug, type_id):
        work_item_type = self.get_object()
        serializer = WorkItemTypeSerializer(work_item_type, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data.get("name")
        if name and IssueType.objects.filter(
            workspace=work_item_type.workspace, name__iexact=name, deleted_at__isnull=True
        ).exclude(pk=work_item_type.pk).exists():
            return Response({"error": "A work item type with this name already exists."}, status=status.HTTP_409_CONFLICT)
        serializer.save()
        return Response(serializer.data)

    @transaction.atomic
    def delete(self, request, slug, type_id):
        work_item_type = self.get_object()
        if Issue.objects.filter(type=work_item_type, deleted_at__isnull=True).exists():
            return Response(
                {"error": "A work item type assigned to work items cannot be deleted. Deactivate it instead."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        work_item_type.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectWorkItemTypeListCreateAPIEndpoint(BaseAPIView):
    """List enabled work-item types in a project or enable one for the project."""

    permission_classes = [ProjectEntityPermission]

    def get_queryset(self):
        return ProjectIssueType.objects.filter(
            workspace__slug=self.kwargs["slug"], project_id=self.kwargs["project_id"], deleted_at__isnull=True,
            issue_type__deleted_at__isnull=True, issue_type__is_active=True,
        ).select_related("issue_type")

    def get(self, request, slug, project_id):
        return self.paginate(
            request=request,
            queryset=self.get_queryset().order_by("level", "issue_type__name"),
            on_results=lambda types: ProjectWorkItemTypeSerializer(types, many=True, fields=self.fields, expand=self.expand).data,
        )

    @transaction.atomic
    def post(self, request, slug, project_id):
        workspace_id = Workspace.objects.only("id").get(slug=slug, deleted_at__isnull=True).id
        serializer = ProjectWorkItemTypeSerializer(data=request.data, context={"workspace_id": workspace_id})
        serializer.is_valid(raise_exception=True)
        work_item_type = serializer.validated_data["issue_type"]
        try:
            project_type, created = ProjectIssueType.objects.get_or_create(
                project_id=project_id,
                issue_type=work_item_type,
                defaults={"level": serializer.validated_data.get("level", 0), "is_default": False},
            )
        except IntegrityError:
            project_type = ProjectIssueType.objects.get(project_id=project_id, issue_type=work_item_type, deleted_at__isnull=True)
            created = False
        if not created:
            return Response({"error": "Work item type is already enabled for this project."}, status=status.HTTP_409_CONFLICT)
        if serializer.validated_data.get("is_default", False):
            ProjectIssueType.objects.filter(project_id=project_id, deleted_at__isnull=True).exclude(pk=project_type.pk).update(is_default=False)
            project_type.is_default = True
            project_type.save(update_fields=["is_default"])
        return Response(ProjectWorkItemTypeSerializer(project_type).data, status=status.HTTP_201_CREATED)


class ProjectWorkItemTypeDetailAPIEndpoint(BaseAPIView):
    """Update project-level settings or disable a work-item type for a project."""

    permission_classes = [ProjectEntityPermission]

    def get_object(self):
        return ProjectIssueType.objects.select_related("issue_type").get(
            pk=self.kwargs["project_type_id"], workspace__slug=self.kwargs["slug"], project_id=self.kwargs["project_id"],
            deleted_at__isnull=True,
        )

    def get(self, request, slug, project_id, project_type_id):
        return Response(ProjectWorkItemTypeSerializer(self.get_object(), fields=self.fields, expand=self.expand).data)

    @transaction.atomic
    def patch(self, request, slug, project_id, project_type_id):
        project_type = self.get_object()
        serializer = ProjectWorkItemTypeSerializer(project_type, data=request.data, partial=True, context={"workspace_id": project_type.workspace_id})
        serializer.is_valid(raise_exception=True)
        if "issue_type" in serializer.validated_data and serializer.validated_data["issue_type"] != project_type.issue_type:
            return Response({"error": "The type link cannot be changed. Create a new link instead."}, status=status.HTTP_400_BAD_REQUEST)
        if serializer.validated_data.get("is_default", False):
            ProjectIssueType.objects.filter(project_id=project_id, deleted_at__isnull=True).exclude(pk=project_type.pk).update(is_default=False)
        serializer.save()
        return Response(serializer.data)

    @transaction.atomic
    def delete(self, request, slug, project_id, project_type_id):
        project_type = self.get_object()
        if Issue.objects.filter(project_id=project_id, type_id=project_type.issue_type_id, deleted_at__isnull=True).exists():
            return Response(
                {"error": "A work item type assigned to project work items cannot be disabled."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        project_type.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
