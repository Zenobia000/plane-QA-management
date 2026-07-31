# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path


from plane.app.views import (
    CycleViewSet,
    CycleIssueViewSet,
    CycleDateCheckEndpoint,
    CycleFavoriteViewSet,
    CycleProgressEndpoint,
    CycleAnalyticsEndpoint,
    TransferCycleIssueEndpoint,
    CycleUserPropertiesEndpoint,
    CycleArchiveUnarchiveEndpoint,
)


urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/cycles/",
        CycleViewSet.as_view({"get": "list", "post": "create"}),
        name="project-cycle",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/cycles/<uuid:pk>/",
        CycleViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="project-cycle",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/cycles/<uuid:cycle_id>/cycle-issues/",
        CycleIssueViewSet.as_view({"get": "list", "post": "create"}),
        name="project-issue-cycle",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/cycles/<uuid:cycle_id>/cycle-issues/<uuid:issue_id>/",
        CycleIssueViewSet.as_view(
            {
                # No `get`: the viewset defines no `retrieve`, and its lookup kwarg is
                # `issue_id` rather than `pk`, so DRF's default raised rather than
                # serving. Nothing called it; the list route above is the read path.
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="project-issue-cycle",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/cycles/date-check/",
        CycleDateCheckEndpoint.as_view(),
        name="project-cycle-date",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/user-favorite-cycles/",
        # GET is not offered: the viewset has no serializer and does not filter by
        # entity_type, so listing here would 500 -- and reading favourites already has
        # a working home at `workspaces/<slug>/user-favorites/`, which is what the web
        # app calls. Only the write pair belongs on this route.
        CycleFavoriteViewSet.as_view({"post": "create"}),
        name="user-favorite-cycle",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/user-favorite-cycles/<uuid:cycle_id>/",
        CycleFavoriteViewSet.as_view({"delete": "destroy"}),
        name="user-favorite-cycle",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/cycles/<uuid:cycle_id>/transfer-issues/",
        TransferCycleIssueEndpoint.as_view(),
        name="transfer-issues",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/cycles/<uuid:cycle_id>/user-properties/",
        CycleUserPropertiesEndpoint.as_view(),
        name="cycle-user-filters",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/cycles/<uuid:cycle_id>/archive/",
        # Restricted to the write pair. `as_view()` on an APIView exposes every method
        # the class defines, and this one's `get` takes `pk` -- it serves the
        # `archived-cycles/` routes below. Reached through this URL it was handed
        # `cycle_id` and raised TypeError, so GET here answered 500 instead of 405.
        CycleArchiveUnarchiveEndpoint.as_view(http_method_names=["post", "delete"]),
        name="cycle-archive-unarchive",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/archived-cycles/",
        CycleArchiveUnarchiveEndpoint.as_view(),
        name="cycle-archive-unarchive",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/archived-cycles/<uuid:pk>/",
        CycleArchiveUnarchiveEndpoint.as_view(),
        name="cycle-archive-unarchive",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/cycles/<uuid:cycle_id>/progress/",
        CycleProgressEndpoint.as_view(),
        name="project-cycle",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/cycles/<uuid:cycle_id>/analytics/",
        CycleAnalyticsEndpoint.as_view(),
        name="project-cycle",
    ),
]
