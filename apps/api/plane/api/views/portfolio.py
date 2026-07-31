# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from plane.api.serializers.portfolio import InitiativeSerializer, MilestoneSerializer
from plane.app.permissions import ProjectEntityPermission, WorkSpaceAdminPermission
from plane.db.models import Initiative, InitiativeProject, Issue, Milestone, Project, Workspace

from .base import BaseAPIView


class MilestoneListCreateAPIEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get_queryset(self):
        return Milestone.objects.filter(
            workspace__slug=self.kwargs["slug"], project_id=self.kwargs["project_id"], deleted_at__isnull=True
        ).order_by("target_date", "sort_order", "created_at")

    def get(self, request, slug, project_id):
        return self.paginate(
            request=request,
            queryset=self.get_queryset(),
            on_results=lambda milestones: MilestoneSerializer(
                milestones, many=True, fields=self.fields, expand=self.expand
            ).data,
        )

    @transaction.atomic
    def post(self, request, slug, project_id):
        serializer = MilestoneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        milestone = serializer.save(project_id=project_id)
        return Response(MilestoneSerializer(milestone).data, status=status.HTTP_201_CREATED)


class MilestoneDetailAPIEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get_object(self):
        return Milestone.objects.get(
            pk=self.kwargs["milestone_id"],
            workspace__slug=self.kwargs["slug"],
            project_id=self.kwargs["project_id"],
            deleted_at__isnull=True,
        )

    def get(self, request, slug, project_id, milestone_id):
        return Response(MilestoneSerializer(self.get_object(), fields=self.fields, expand=self.expand).data)

    @transaction.atomic
    def patch(self, request, slug, project_id, milestone_id):
        serializer = MilestoneSerializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @transaction.atomic
    def delete(self, request, slug, project_id, milestone_id):
        milestone = self.get_object()
        if Issue.objects.filter(milestone=milestone, deleted_at__isnull=True).exists():
            return Response(
                {"error": "A milestone assigned to work items cannot be deleted."}, status=status.HTTP_400_BAD_REQUEST
            )
        milestone.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class InitiativeListCreateAPIEndpoint(BaseAPIView):
    permission_classes = [WorkSpaceAdminPermission]

    def get_queryset(self):
        return Initiative.objects.filter(workspace__slug=self.kwargs["slug"], deleted_at__isnull=True).prefetch_related(
            "initiative_projects__project"
        )

    def get(self, request, slug):
        return self.paginate(
            request=request,
            queryset=self.get_queryset().order_by("target_date", "sort_order", "created_at"),
            on_results=lambda initiatives: InitiativeSerializer(
                initiatives, many=True, fields=self.fields, expand=self.expand
            ).data,
        )

    @transaction.atomic
    def post(self, request, slug):
        workspace = Workspace.objects.get(slug=slug, deleted_at__isnull=True)
        serializer = InitiativeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project_ids = serializer.validated_data.pop("project_ids", [])
        projects = _workspace_projects_or_error(workspace, project_ids)
        initiative = serializer.save(workspace=workspace)
        _replace_initiative_projects(initiative, projects)
        return Response(InitiativeSerializer(initiative).data, status=status.HTTP_201_CREATED)


class InitiativeDetailAPIEndpoint(BaseAPIView):
    permission_classes = [WorkSpaceAdminPermission]

    def get_object(self):
        return Initiative.objects.prefetch_related("initiative_projects__project").get(
            pk=self.kwargs["initiative_id"], workspace__slug=self.kwargs["slug"], deleted_at__isnull=True
        )

    def get(self, request, slug, initiative_id):
        return Response(InitiativeSerializer(self.get_object(), fields=self.fields, expand=self.expand).data)

    @transaction.atomic
    def patch(self, request, slug, initiative_id):
        initiative = self.get_object()
        serializer = InitiativeSerializer(initiative, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        project_ids = serializer.validated_data.pop("project_ids", None)
        if project_ids is not None:
            _replace_initiative_projects(initiative, _workspace_projects_or_error(initiative.workspace, project_ids))
        serializer.save()
        return Response(InitiativeSerializer(initiative).data)

    @transaction.atomic
    def delete(self, request, slug, initiative_id):
        initiative = self.get_object()
        initiative.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _workspace_projects_or_error(workspace, project_ids):
    if len(project_ids) != len(set(project_ids)):
        from rest_framework.exceptions import ValidationError

        raise ValidationError({"project_ids": "Project IDs must be unique."})
    projects = list(Project.objects.filter(workspace=workspace, id__in=project_ids, deleted_at__isnull=True))
    if len(projects) != len(project_ids):
        from rest_framework.exceptions import ValidationError

        raise ValidationError({"project_ids": "Every project must belong to this workspace."})
    return projects


def _replace_initiative_projects(initiative, projects):
    project_ids = [project.id for project in projects]
    InitiativeProject.objects.filter(initiative=initiative, deleted_at__isnull=True).exclude(
        project_id__in=project_ids
    ).delete()
    existing_project_ids = set(
        InitiativeProject.objects.filter(initiative=initiative, deleted_at__isnull=True).values_list(
            "project_id", flat=True
        )
    )
    InitiativeProject.objects.bulk_create(
        [
            InitiativeProject(initiative=initiative, project=project, workspace=initiative.workspace)
            for project in projects
            if project.id not in existing_project_ids
        ]
    )
