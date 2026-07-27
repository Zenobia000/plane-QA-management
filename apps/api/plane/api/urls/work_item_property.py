# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.urls import path

from plane.api.views.work_item_property import (
    WorkItemPropertyDetailAPIEndpoint,
    WorkItemPropertyListCreateAPIEndpoint,
    WorkItemPropertyValueDetailAPIEndpoint,
    WorkItemPropertyValueListAPIEndpoint,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-properties/",
        WorkItemPropertyListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="work-item-properties",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-properties/<uuid:property_id>/",
        WorkItemPropertyDetailAPIEndpoint.as_view(http_method_names=["get", "patch", "delete"]),
        name="work-item-property",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-items/<uuid:issue_id>/properties/",
        WorkItemPropertyValueListAPIEndpoint.as_view(http_method_names=["get"]),
        name="work-item-property-values",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-items/<uuid:issue_id>/properties/<uuid:property_id>/",
        WorkItemPropertyValueDetailAPIEndpoint.as_view(http_method_names=["put", "delete"]),
        name="work-item-property-value",
    ),
]
