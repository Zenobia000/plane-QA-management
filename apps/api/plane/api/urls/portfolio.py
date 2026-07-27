# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.urls import path

from plane.api.views.portfolio import (
    InitiativeDetailAPIEndpoint,
    InitiativeListCreateAPIEndpoint,
    MilestoneDetailAPIEndpoint,
    MilestoneListCreateAPIEndpoint,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/initiatives/",
        InitiativeListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="initiatives",
    ),
    path(
        "workspaces/<str:slug>/initiatives/<uuid:initiative_id>/",
        InitiativeDetailAPIEndpoint.as_view(http_method_names=["get", "patch", "delete"]),
        name="initiative",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/milestones/",
        MilestoneListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="milestones",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/milestones/<uuid:milestone_id>/",
        MilestoneDetailAPIEndpoint.as_view(http_method_names=["get", "patch", "delete"]),
        name="milestone",
    ),
]
