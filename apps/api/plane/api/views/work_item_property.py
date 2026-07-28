# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from plane.api.middleware.api_authentication import APIKeyAuthentication
from plane.api.rate_limit import ApiKeyRateThrottle
from plane.app.views.work_item_property import (
    WorkItemPropertyDetailEndpoint as AppWorkItemPropertyDetailEndpoint,
    WorkItemPropertyListCreateEndpoint as AppWorkItemPropertyListCreateEndpoint,
    WorkItemPropertyValueDetailEndpoint as AppWorkItemPropertyValueDetailEndpoint,
    WorkItemPropertyValueListEndpoint as AppWorkItemPropertyValueListEndpoint,
)


class APIKeyWorkItemPropertyEndpointMixin:
    authentication_classes = [APIKeyAuthentication]

    def get_throttles(self):
        return [ApiKeyRateThrottle()]


class WorkItemPropertyListCreateAPIEndpoint(APIKeyWorkItemPropertyEndpointMixin, AppWorkItemPropertyListCreateEndpoint):
    pass


class WorkItemPropertyDetailAPIEndpoint(APIKeyWorkItemPropertyEndpointMixin, AppWorkItemPropertyDetailEndpoint):
    pass


class WorkItemPropertyValueListAPIEndpoint(APIKeyWorkItemPropertyEndpointMixin, AppWorkItemPropertyValueListEndpoint):
    pass


class WorkItemPropertyValueDetailAPIEndpoint(
    APIKeyWorkItemPropertyEndpointMixin, AppWorkItemPropertyValueDetailEndpoint
):
    pass
