# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.urls import path

from plane.api.views import (
    ProjectViewDetailAPIEndpoint,
    ProjectViewListCreateAPIEndpoint,
    WorkspaceViewDetailAPIEndpoint,
    WorkspaceViewListCreateAPIEndpoint,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/views/",
        ProjectViewListCreateAPIEndpoint.as_view(),
        name="api-project-views",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/views/<uuid:pk>/",
        ProjectViewDetailAPIEndpoint.as_view(),
        name="api-project-view-detail",
    ),
    path(
        "workspaces/<str:slug>/views/",
        WorkspaceViewListCreateAPIEndpoint.as_view(),
        name="api-workspace-views",
    ),
    path(
        "workspaces/<str:slug>/views/<uuid:pk>/",
        WorkspaceViewDetailAPIEndpoint.as_view(),
        name="api-workspace-view-detail",
    ),
]
