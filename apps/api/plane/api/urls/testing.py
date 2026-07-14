# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.urls import path

from plane.api.views.testing import AutomationIngestionEndpoint

urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/testing/automation-ingestions/",
        AutomationIngestionEndpoint.as_view(),
        name="testing-automation-ingestions",
    )
]
