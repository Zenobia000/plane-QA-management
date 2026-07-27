# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.urls import path

from plane.api.views.work_item_type import (
    ProjectWorkItemTypeDetailAPIEndpoint,
    ProjectWorkItemTypeListCreateAPIEndpoint,
    WorkItemTypeDetailAPIEndpoint,
    WorkItemTypeListCreateAPIEndpoint,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/work-item-types/",
        WorkItemTypeListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="work-item-types",
    ),
    path(
        "workspaces/<str:slug>/work-item-types/<uuid:type_id>/",
        WorkItemTypeDetailAPIEndpoint.as_view(http_method_names=["get", "patch", "delete"]),
        name="work-item-type",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/",
        ProjectWorkItemTypeListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="project-work-item-types",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/<uuid:project_type_id>/",
        ProjectWorkItemTypeDetailAPIEndpoint.as_view(http_method_names=["get", "patch", "delete"]),
        name="project-work-item-type",
    ),
]
