# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from plane.api.middleware.api_authentication import APIKeyAuthentication
from plane.api.rate_limit import ApiKeyRateThrottle
from plane.app.permissions import WorkSpaceAdminPermission
from plane.app.views.work_item_type import (
    ProjectWorkItemTypeDetailEndpoint as AppProjectWorkItemTypeDetailEndpoint,
    ProjectWorkItemTypeListCreateEndpoint as AppProjectWorkItemTypeListCreateEndpoint,
    WorkItemTypeDetailEndpoint as AppWorkItemTypeDetailEndpoint,
    WorkItemTypeListCreateEndpoint as AppWorkItemTypeListCreateEndpoint,
)


class APIKeyWorkItemTypeEndpointMixin:
    authentication_classes = [APIKeyAuthentication]

    def get_throttles(self):
        return [ApiKeyRateThrottle()]


class WorkItemTypeListCreateAPIEndpoint(APIKeyWorkItemTypeEndpointMixin, AppWorkItemTypeListCreateEndpoint):
    permission_classes = [WorkSpaceAdminPermission]


class WorkItemTypeDetailAPIEndpoint(APIKeyWorkItemTypeEndpointMixin, AppWorkItemTypeDetailEndpoint):
    permission_classes = [WorkSpaceAdminPermission]


class ProjectWorkItemTypeListCreateAPIEndpoint(
    APIKeyWorkItemTypeEndpointMixin, AppProjectWorkItemTypeListCreateEndpoint
):
    pass


class ProjectWorkItemTypeDetailAPIEndpoint(APIKeyWorkItemTypeEndpointMixin, AppProjectWorkItemTypeDetailEndpoint):
    pass
