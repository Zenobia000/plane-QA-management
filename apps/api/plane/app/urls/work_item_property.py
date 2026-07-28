# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.urls import path

from plane.app.views.work_item_property import (
    WorkItemPropertyDetailEndpoint,
    WorkItemPropertyListCreateEndpoint,
    WorkItemPropertyValueDetailEndpoint,
    WorkItemPropertyValueListEndpoint,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-properties/",
        WorkItemPropertyListCreateEndpoint.as_view(),
        name="app-work-item-properties",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-properties/<uuid:property_id>/",
        WorkItemPropertyDetailEndpoint.as_view(),
        name="app-work-item-property",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-items/<uuid:issue_id>/properties/",
        WorkItemPropertyValueListEndpoint.as_view(),
        name="app-work-item-property-values",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-items/<uuid:issue_id>/properties/<uuid:property_id>/",
        WorkItemPropertyValueDetailEndpoint.as_view(),
        name="app-work-item-property-value",
    ),
]
