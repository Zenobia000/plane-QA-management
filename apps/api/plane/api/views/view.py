# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from uuid import uuid4

from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from plane.api.middleware.api_authentication import APIKeyAuthentication
from plane.api.rate_limit import ApiKeyRateThrottle
from plane.app.permissions import ProjectEntityPermission, WorkspaceEntityPermission
from plane.app.serializers import IssueViewSerializer
from plane.db.models import IssueView, Project, Workspace

from .base import BaseAPIView


class APIKeyViewEndpointMixin:
    """Expose saved views through the public API-key boundary.

    The app viewsets are not reused here the way the testing endpoints reuse
    theirs: they annotate per-user favourites and apply guest-visibility rules
    that only mean something inside a browser session. An API key acts for its
    owner, so the visibility rule that survives is the model's own -- your views
    plus every public one.
    """

    authentication_classes = [APIKeyAuthentication]

    def get_throttles(self):
        return [ApiKeyRateThrottle()]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        response["X-Request-ID"] = request_id
        if response.status_code < 400:
            return response

        payload = response.data
        if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
            payload["error"].setdefault("request_id", request_id)
            return response

        if isinstance(payload, dict):
            raw_message = payload.get("error") or payload.get("detail") or payload
        else:
            raw_message = payload
        message = raw_message if isinstance(raw_message, str) else "The request could not be completed."
        response.data = {
            "error": {
                "code": f"http_{response.status_code}",
                "message": message,
                "details": payload,
                "request_id": request_id,
            }
        }
        return response

    def visible(self, queryset, request):
        return queryset.filter(Q(owned_by=request.user) | Q(access=1))


class ProjectViewListCreateAPIEndpoint(APIKeyViewEndpointMixin, BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        views = self.visible(
            IssueView.objects.filter(workspace__slug=slug, project_id=project_id), request
        ).order_by("sort_order", "name")
        return Response(IssueViewSerializer(views, many=True).data)

    def post(self, request, slug, project_id):
        project = Project.objects.get(id=project_id, workspace__slug=slug)
        serializer = IssueViewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # `query` is derived from `filters` by the serializer, and `access` and
        # `is_locked` are read-only there, so both are set explicitly.
        view = serializer.save(
            workspace_id=project.workspace_id,
            project_id=project.id,
            owned_by=request.user,
            access=request.data.get("access", 1),
            is_locked=request.data.get("is_locked", False),
        )
        return Response(IssueViewSerializer(view).data, status=status.HTTP_201_CREATED)


class ProjectViewDetailAPIEndpoint(APIKeyViewEndpointMixin, BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def _get(self, request, slug, project_id, pk):
        return self.visible(
            IssueView.objects.filter(workspace__slug=slug, project_id=project_id, pk=pk), request
        ).first()

    def get(self, request, slug, project_id, pk):
        view = self._get(request, slug, project_id, pk)
        if view is None:
            return Response({"error": "The view does not exist."}, status=status.HTTP_404_NOT_FOUND)
        return Response(IssueViewSerializer(view).data)

    def patch(self, request, slug, project_id, pk):
        view = self._get(request, slug, project_id, pk)
        if view is None:
            return Response({"error": "The view does not exist."}, status=status.HTTP_404_NOT_FOUND)
        if view.is_locked:
            return Response({"error": "A locked view cannot be updated."}, status=status.HTTP_409_CONFLICT)
        serializer = IssueViewSerializer(view, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        for field in ("access", "is_locked"):
            if field in request.data:
                setattr(updated, field, request.data[field])
        updated.save()
        return Response(IssueViewSerializer(updated).data)

    def delete(self, request, slug, project_id, pk):
        view = IssueView.objects.filter(workspace__slug=slug, project_id=project_id, pk=pk).first()
        if view is None:
            return Response({"error": "The view does not exist."}, status=status.HTTP_404_NOT_FOUND)
        # Deleting someone else's saved view is not something a token should do
        # quietly, so ownership is required rather than project membership.
        if view.owned_by_id != request.user.id:
            return Response(
                {"error": "Only the owner can delete this view."}, status=status.HTTP_403_FORBIDDEN
            )
        view.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceViewListCreateAPIEndpoint(APIKeyViewEndpointMixin, BaseAPIView):
    permission_classes = [WorkspaceEntityPermission]

    def get(self, request, slug):
        views = self.visible(
            IssueView.objects.filter(workspace__slug=slug, project__isnull=True), request
        ).order_by("sort_order", "name")
        return Response(IssueViewSerializer(views, many=True).data)

    def post(self, request, slug):
        workspace = Workspace.objects.get(slug=slug)
        serializer = IssueViewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        view = serializer.save(
            workspace_id=workspace.id,
            project_id=None,
            owned_by=request.user,
            access=request.data.get("access", 1),
            is_locked=request.data.get("is_locked", False),
        )
        return Response(IssueViewSerializer(view).data, status=status.HTTP_201_CREATED)


class WorkspaceViewDetailAPIEndpoint(APIKeyViewEndpointMixin, BaseAPIView):
    permission_classes = [WorkspaceEntityPermission]

    def _get(self, request, slug, pk):
        return self.visible(
            IssueView.objects.filter(workspace__slug=slug, project__isnull=True, pk=pk), request
        ).first()

    def get(self, request, slug, pk):
        view = self._get(request, slug, pk)
        if view is None:
            return Response({"error": "The view does not exist."}, status=status.HTTP_404_NOT_FOUND)
        return Response(IssueViewSerializer(view).data)

    def patch(self, request, slug, pk):
        view = self._get(request, slug, pk)
        if view is None:
            return Response({"error": "The view does not exist."}, status=status.HTTP_404_NOT_FOUND)
        if view.is_locked:
            return Response({"error": "A locked view cannot be updated."}, status=status.HTTP_409_CONFLICT)
        serializer = IssueViewSerializer(view, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        for field in ("access", "is_locked"):
            if field in request.data:
                setattr(updated, field, request.data[field])
        updated.save()
        return Response(IssueViewSerializer(updated).data)

    def delete(self, request, slug, pk):
        view = IssueView.objects.filter(workspace__slug=slug, project__isnull=True, pk=pk).first()
        if view is None:
            return Response({"error": "The view does not exist."}, status=status.HTTP_404_NOT_FOUND)
        if view.owned_by_id != request.user.id:
            return Response(
                {"error": "Only the owner can delete this view."}, status=status.HTTP_403_FORBIDDEN
            )
        view.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
