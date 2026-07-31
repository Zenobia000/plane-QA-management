# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path


from plane.app.views import (
    ModuleViewSet,
    ModuleIssueViewSet,
    ModuleLinkViewSet,
    ModuleFavoriteViewSet,
    ModuleUserPropertiesEndpoint,
    ModuleArchiveUnarchiveEndpoint,
)


urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/modules/",
        ModuleViewSet.as_view({"get": "list", "post": "create"}),
        name="project-modules",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/modules/<uuid:pk>/",
        ModuleViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="project-modules",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issues/<uuid:issue_id>/modules/",
        ModuleIssueViewSet.as_view({"post": "create_issue_modules"}),
        name="issue-module",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/modules/<uuid:module_id>/issues/",
        ModuleIssueViewSet.as_view({"post": "create_module_issues", "get": "list"}),
        name="project-module-issues",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/modules/<uuid:module_id>/issues/<uuid:issue_id>/",
        ModuleIssueViewSet.as_view(
            {
                # No `get`: the viewset defines no `retrieve`, and its lookup kwarg is
                # `issue_id` rather than `pk`, so DRF's default raised rather than
                # serving. Nothing called it; the list route above is the read path.
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="project-module-issues",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/modules/<uuid:module_id>/module-links/",
        ModuleLinkViewSet.as_view({"get": "list", "post": "create"}),
        name="project-issue-module-links",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/modules/<uuid:module_id>/module-links/<uuid:pk>/",
        ModuleLinkViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="project-issue-module-links",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/user-favorite-modules/",
        # GET is not offered: the viewset has no serializer and does not filter by
        # entity_type, so listing here would 500 -- and reading favourites already has
        # a working home at `workspaces/<slug>/user-favorites/`, which is what the web
        # app calls. Only the write pair belongs on this route.
        ModuleFavoriteViewSet.as_view({"post": "create"}),
        name="user-favorite-module",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/user-favorite-modules/<uuid:module_id>/",
        ModuleFavoriteViewSet.as_view({"delete": "destroy"}),
        name="user-favorite-module",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/modules/<uuid:module_id>/user-properties/",
        ModuleUserPropertiesEndpoint.as_view(),
        name="cycle-user-filters",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/modules/<uuid:module_id>/archive/",
        # Restricted to the write pair. `as_view()` on an APIView exposes every method
        # the class defines, and this one's `get` takes `pk` -- it serves the
        # `archived-modules/` routes below. Reached through this URL it was handed
        # `module_id` and raised TypeError, so GET here answered 500 instead of 405.
        ModuleArchiveUnarchiveEndpoint.as_view(http_method_names=["post", "delete"]),
        name="module-archive-unarchive",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/archived-modules/",
        ModuleArchiveUnarchiveEndpoint.as_view(),
        name="module-archive-unarchive",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/archived-modules/<uuid:pk>/",
        ModuleArchiveUnarchiveEndpoint.as_view(),
        name="module-archive-unarchive",
    ),
]
