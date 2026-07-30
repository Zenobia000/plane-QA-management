# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Dashboards, and the aggregate each widget asks for.

A widget stores a question and this computes the answer on read. Nothing is cached: a
dashboard that stores counts is a dashboard that is wrong between refreshes, and each of
these is a single grouped aggregate over tables the work-item list already queries constantly.

Widget scope is by project, and an empty `project_ids` means every project the *requesting
user* is a member of -- not every project in the workspace. A dashboard is a view of your own
work, and one that counted projects you cannot open would report totals you have no way to
reconcile.
"""

# Django imports
from django.db.models import Count

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import WorkspaceEntityPermission
from plane.app.serializers.base import BaseSerializer
from plane.app.views.base import BaseAPIView, BaseViewSet
from plane.db.models import Dashboard, DashboardWidget, Issue, Project, Workspace

GROUP_FIELDS = {
    "state_group": ("state__group", "state__group"),
    "priority": ("priority", "priority"),
    "assignee": ("assignees__id", "assignees__display_name"),
    "project": ("project_id", "project__name"),
}


class DashboardWidgetSerializer(BaseSerializer):
    class Meta:
        model = DashboardWidget
        fields = "__all__"
        read_only_fields = ["workspace", "dashboard"]


class DashboardSerializer(BaseSerializer):
    class Meta:
        model = Dashboard
        fields = "__all__"
        read_only_fields = ["workspace", "owned_by"]


class DashboardViewSet(BaseViewSet):
    permission_classes = [WorkspaceEntityPermission]
    model = Dashboard
    serializer_class = DashboardSerializer

    def get_queryset(self):
        from django.db.models import Q

        return (
            super()
            .get_queryset()
            .filter(workspace__slug=self.kwargs.get("slug"))
            # Same visibility rule saved views use, so one mental model covers both.
            .filter(Q(owned_by=self.request.user) | Q(access=1))
            .prefetch_related("widgets")
        )

    def perform_create(self, serializer):
        workspace = Workspace.objects.get(slug=self.kwargs.get("slug"))
        serializer.save(workspace=workspace, owned_by=self.request.user)


class DashboardWidgetViewSet(BaseViewSet):
    permission_classes = [WorkspaceEntityPermission]
    model = DashboardWidget
    serializer_class = DashboardWidgetSerializer

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(workspace__slug=self.kwargs.get("slug"), dashboard_id=self.kwargs.get("dashboard_id"))
        )

    def perform_create(self, serializer):
        dashboard = Dashboard.objects.get(pk=self.kwargs.get("dashboard_id"))
        serializer.save(dashboard=dashboard, workspace=dashboard.workspace)


class DashboardWidgetDataEndpoint(BaseAPIView):
    """The answer to one widget's question, computed now."""

    permission_classes = [WorkspaceEntityPermission]

    def get(self, request, slug, dashboard_id, widget_id):
        widget = DashboardWidget.objects.filter(
            pk=widget_id, dashboard_id=dashboard_id, workspace__slug=slug
        ).first()
        if not widget:
            return Response({"error": "The widget does not exist."}, status=status.HTTP_404_NOT_FOUND)

        # Scope is intersected with the caller's own memberships rather than trusted from the
        # widget, so a widget cannot be used to count projects the reader cannot open.
        readable = set(
            Project.objects.filter(
                workspace__slug=slug,
                project_projectmember__member=request.user,
                project_projectmember__is_active=True,
            ).values_list("id", flat=True)
        )
        scoped = (
            {pid for pid in readable if str(pid) in {str(p) for p in widget.project_ids}}
            if widget.project_ids
            else readable
        )

        key_field, label_field = GROUP_FIELDS[widget.group_by]
        rows = (
            Issue.issue_objects.filter(project_id__in=scoped)
            .values(key_field, label_field)
            .annotate(count=Count("id", distinct=True))
            .order_by("-count")
        )

        return Response(
            {
                "widget_id": str(widget.id),
                "group_by": widget.group_by,
                "chart": widget.chart,
                "total": sum(row["count"] for row in rows),
                "series": [
                    {
                        "key": str(row[key_field]) if row[key_field] is not None else "none",
                        "label": str(row[label_field]) if row[label_field] is not None else "None",
                        "count": row["count"],
                    }
                    for row in rows
                ],
            },
            status=status.HTTP_200_OK,
        )
