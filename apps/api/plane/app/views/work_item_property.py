# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from plane.api.serializers.work_item_property import (
    WorkItemPropertySerializer,
    WorkItemPropertyValueSerializer,
    validate_property_value,
)
from plane.app.permissions import ProjectEntityPermission
from plane.app.views.base import BaseAPIView
from plane.db.models import Issue, WorkItemProperty, WorkItemPropertyValue


class WorkItemPropertyListCreateEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get_queryset(self):
        return (
            WorkItemProperty.objects.filter(
                workspace__slug=self.kwargs["slug"],
                project_id=self.kwargs["project_id"],
                deleted_at__isnull=True,
            )
            .prefetch_related("options")
            .order_by("sort_order", "created_at")
        )

    def get(self, request, slug, project_id):
        return self.paginate(
            request=request,
            queryset=self.get_queryset(),
            on_results=lambda properties: (
                WorkItemPropertySerializer(properties, many=True, fields=self.fields, expand=self.expand).data
            ),
        )

    @transaction.atomic
    def post(self, request, slug, project_id):
        serializer = WorkItemPropertySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        property_definition = serializer.save(project_id=project_id)
        return Response(WorkItemPropertySerializer(property_definition).data, status=status.HTTP_201_CREATED)


class WorkItemPropertyDetailEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get_object(self):
        return WorkItemProperty.objects.prefetch_related("options").get(
            pk=self.kwargs["property_id"],
            workspace__slug=self.kwargs["slug"],
            project_id=self.kwargs["project_id"],
            deleted_at__isnull=True,
        )

    def get(self, request, slug, project_id, property_id):
        return Response(WorkItemPropertySerializer(self.get_object(), fields=self.fields, expand=self.expand).data)

    @transaction.atomic
    def patch(self, request, slug, project_id, property_id):
        property_definition = self.get_object()
        serializer = WorkItemPropertySerializer(property_definition, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        next_kind = serializer.validated_data.get("kind", property_definition.kind)
        if (
            next_kind != property_definition.kind
            and property_definition.values.filter(deleted_at__isnull=True).exists()
        ):
            return Response(
                {"error": "A property with values cannot change its kind."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save()
        return Response(serializer.data)

    @transaction.atomic
    def delete(self, request, slug, project_id, property_id):
        property_definition = self.get_object()
        if property_definition.values.filter(deleted_at__isnull=True).exists():
            return Response(
                {"error": "A property with values cannot be deleted. Deactivate it instead."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        property_definition.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkItemPropertyValueListEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get_issue(self):
        return Issue.objects.get(
            pk=self.kwargs["issue_id"],
            workspace__slug=self.kwargs["slug"],
            project_id=self.kwargs["project_id"],
            deleted_at__isnull=True,
        )

    def get(self, request, slug, project_id, issue_id):
        issue = self.get_issue()
        values = WorkItemPropertyValue.objects.filter(issue=issue, deleted_at__isnull=True).select_related("property")
        return self.paginate(
            request=request,
            queryset=values,
            on_results=lambda property_values: (
                WorkItemPropertyValueSerializer(property_values, many=True, fields=self.fields, expand=self.expand).data
            ),
        )


class WorkItemPropertyValueDetailEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get_issue_and_property(self):
        issue = Issue.objects.get(
            pk=self.kwargs["issue_id"],
            workspace__slug=self.kwargs["slug"],
            project_id=self.kwargs["project_id"],
            deleted_at__isnull=True,
        )
        property_definition = WorkItemProperty.objects.prefetch_related("options").get(
            pk=self.kwargs["property_id"],
            workspace__slug=self.kwargs["slug"],
            project_id=self.kwargs["project_id"],
            deleted_at__isnull=True,
            is_active=True,
        )
        # This endpoint writes a value directly, without going through the work-item
        # serializer, so it is the other way a property could be set on an item its type
        # never asks for. Refused here rather than left to the UI, which is a suggestion.
        if property_definition.type_id is not None and property_definition.type_id != issue.type_id:
            raise ValidationError({"property": "This property does not apply to this work item's type."})
        return issue, property_definition

    @transaction.atomic
    def put(self, request, slug, project_id, issue_id, property_id):
        issue, property_definition = self.get_issue_and_property()
        value = validate_property_value(property_definition, request.data.get("value"))
        property_value, _ = WorkItemPropertyValue.objects.update_or_create(
            issue=issue,
            property=property_definition,
            defaults={"project": issue.project, "workspace": issue.workspace, "value": value},
        )
        return Response(WorkItemPropertyValueSerializer(property_value).data)

    @transaction.atomic
    def delete(self, request, slug, project_id, issue_id, property_id):
        issue, property_definition = self.get_issue_and_property()
        property_value = WorkItemPropertyValue.objects.filter(
            issue=issue, property=property_definition, deleted_at__isnull=True
        ).first()
        if property_value is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        if property_definition.is_required:
            return Response(
                {"error": "A required work item property cannot be cleared."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        property_value.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
