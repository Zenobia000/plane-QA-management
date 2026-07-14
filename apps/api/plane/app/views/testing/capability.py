# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework.response import Response

from plane.app.permissions import ProjectEntityPermission
from plane.app.views.base import BaseAPIView


class TestingCapabilityEndpoint(BaseAPIView):
    """Expose the native Testing surface supported by this fork."""

    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        return Response(
            {
                "enabled": True,
                "stage": "manual-quality-loop",
                "capabilities": {
                    "test_cases": True,
                    "test_runs": True,
                    "reports": True,
                    "automation_ingestion": True,
                },
            }
        )
