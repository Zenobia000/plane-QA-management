# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.urls import path

from plane.app.views.work_item_type import (
    ProjectWorkItemTypeDetailEndpoint,
    ProjectWorkItemTypeListCreateEndpoint,
    WorkItemTypeDetailEndpoint,
    WorkItemTypeListCreateEndpoint,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/work-item-types/",
        WorkItemTypeListCreateEndpoint.as_view(),
        name="app-work-item-types",
    ),
    path(
        "workspaces/<str:slug>/work-item-types/<uuid:type_id>/",
        WorkItemTypeDetailEndpoint.as_view(),
        name="app-work-item-type",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/",
        ProjectWorkItemTypeListCreateEndpoint.as_view(),
        name="app-project-work-item-types",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/<uuid:project_type_id>/",
        ProjectWorkItemTypeDetailEndpoint.as_view(),
        name="app-project-work-item-type",
    ),
]
