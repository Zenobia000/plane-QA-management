# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from uuid import uuid4

from rest_framework import status
from rest_framework.response import Response

from plane.api.serializers.testing import AutomationIngestionSerializer
from plane.api.middleware.api_authentication import APIKeyAuthentication
from plane.api.rate_limit import ApiKeyRateThrottle
from plane.app.views.testing import (
    TestCaseAttachmentEndpoint as AppTestCaseAttachmentEndpoint,
    TestCaseDetailEndpoint as AppTestCaseDetailEndpoint,
    TestCaseListCreateEndpoint as AppTestCaseListCreateEndpoint,
    TestCaseVersionDetailEndpoint as AppTestCaseVersionDetailEndpoint,
    TestCaseWorkItemLinkDetailEndpoint as AppTestCaseWorkItemLinkDetailEndpoint,
    TestCaseWorkItemLinkEndpoint as AppTestCaseWorkItemLinkEndpoint,
    TestFolderDetailEndpoint as AppTestFolderDetailEndpoint,
    TestFolderListCreateEndpoint as AppTestFolderListCreateEndpoint,
    TestResultDefectEndpoint as AppTestResultDefectEndpoint,
    TestRunCloseEndpoint as AppTestRunCloseEndpoint,
    TestRunDetailEndpoint as AppTestRunDetailEndpoint,
    TestRunListCreateEndpoint as AppTestRunListCreateEndpoint,
    TestRunResultEndpoint as AppTestRunResultEndpoint,
    TestingCapabilityEndpoint as AppTestingCapabilityEndpoint,
    TestingOverviewEndpoint as AppTestingOverviewEndpoint,
    TestingRequirementCoverageEndpoint as AppTestingRequirementCoverageEndpoint,
    TestLibraryExportEndpoint as AppTestLibraryExportEndpoint,
    TestLibrarySearchEndpoint as AppTestLibrarySearchEndpoint,
)
from plane.app.permissions import ProjectEntityPermission
from plane.testing import IdempotencyConflict, ingest_automation_results, parse_junit_xml, serialize_ingestion_response

from .base import BaseAPIView


def _readable(raw):
    """The server's own words where there are any, the generic line only as a last resort.

    Django raises `ValidationError`, whose `.messages` is a **list**, and every refusal in
    the availability surface arrives that way -- so a string-only check meant a person read
    "core hours must fall inside the working window" in the browser while the CLI and MCP
    got "The request could not be completed." The reason was in `details` all along, but the
    field every caller prints is `message`.

    DRF field errors are a dict of lists (`{"start_date": ["This field is required."]}`), so
    those are flattened with their field name rather than dropped.
    """
    if isinstance(raw, str):
        return raw

    if isinstance(raw, (list, tuple)):
        parts = [str(item) for item in raw if isinstance(item, (str, int, float))]
        if parts:
            return " ".join(parts)

    if isinstance(raw, dict):
        parts = []
        for field, value in raw.items():
            rendered = _readable(value)
            if rendered and rendered != FALLBACK_MESSAGE:
                parts.append(rendered if field == "error" else f"{field}: {rendered}")
        if parts:
            return " ".join(parts)

    return FALLBACK_MESSAGE


FALLBACK_MESSAGE = "The request could not be completed."


class APIKeyTestingEndpointMixin:
    """Expose the shared Testing handlers through the public API-key boundary."""

    authentication_classes = [APIKeyAuthentication]

    def get_throttles(self):
        return [ApiKeyRateThrottle()]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        response["X-Request-ID"] = request_id
        if response.status_code < 400:
            return response

        payload = response.data
        if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
            payload["error"].setdefault("request_id", request_id)
            return response

        if isinstance(payload, dict):
            raw_message = payload.get("error") or payload.get("detail") or payload
        else:
            raw_message = payload
        message = _readable(raw_message)
        response.data = {
            "error": {
                "code": f"http_{response.status_code}",
                "message": message,
                "details": payload,
                "request_id": request_id,
            }
        }
        return response


class TestingCapabilityAPIEndpoint(APIKeyTestingEndpointMixin, AppTestingCapabilityEndpoint):
    pass


class TestingOverviewAPIEndpoint(APIKeyTestingEndpointMixin, AppTestingOverviewEndpoint):
    pass


class TestingRequirementCoverageAPIEndpoint(APIKeyTestingEndpointMixin, AppTestingRequirementCoverageEndpoint):
    pass


class TestFolderListCreateAPIEndpoint(APIKeyTestingEndpointMixin, AppTestFolderListCreateEndpoint):
    pass


class TestFolderDetailAPIEndpoint(APIKeyTestingEndpointMixin, AppTestFolderDetailEndpoint):
    pass


class TestCaseListCreateAPIEndpoint(APIKeyTestingEndpointMixin, AppTestCaseListCreateEndpoint):
    pass


class TestLibrarySearchAPIEndpoint(APIKeyTestingEndpointMixin, AppTestLibrarySearchEndpoint):
    pass


class TestLibraryExportAPIEndpoint(APIKeyTestingEndpointMixin, AppTestLibraryExportEndpoint):
    pass


class TestCaseDetailAPIEndpoint(APIKeyTestingEndpointMixin, AppTestCaseDetailEndpoint):
    pass


class TestCaseAttachmentAPIEndpoint(APIKeyTestingEndpointMixin, AppTestCaseAttachmentEndpoint):
    pass


class TestCaseVersionDetailAPIEndpoint(APIKeyTestingEndpointMixin, AppTestCaseVersionDetailEndpoint):
    pass


class TestCaseWorkItemLinkAPIEndpoint(APIKeyTestingEndpointMixin, AppTestCaseWorkItemLinkEndpoint):
    pass


class TestCaseWorkItemLinkDetailAPIEndpoint(APIKeyTestingEndpointMixin, AppTestCaseWorkItemLinkDetailEndpoint):
    pass


class TestRunListCreateAPIEndpoint(APIKeyTestingEndpointMixin, AppTestRunListCreateEndpoint):
    pass


class TestRunDetailAPIEndpoint(APIKeyTestingEndpointMixin, AppTestRunDetailEndpoint):
    pass


class TestRunResultAPIEndpoint(APIKeyTestingEndpointMixin, AppTestRunResultEndpoint):
    pass


class TestResultDefectAPIEndpoint(APIKeyTestingEndpointMixin, AppTestResultDefectEndpoint):
    pass


class TestRunCloseAPIEndpoint(APIKeyTestingEndpointMixin, AppTestRunCloseEndpoint):
    pass


class AutomationIngestionEndpoint(APIKeyTestingEndpointMixin, BaseAPIView):
    permission_classes = [ProjectEntityPermission]
    serializer_class = AutomationIngestionSerializer

    def post(self, request, slug, project_id):
        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        if not idempotency_key:
            return Response({"error": "Idempotency-Key header is required."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        results = parse_junit_xml(data.pop("junit_xml")) if data.pop("format") == "junit" else data.pop("results")
        try:
            ingestion, replayed = ingest_automation_results(
                project_id=project_id,
                idempotency_key=idempotency_key,
                results=results,
                created_by=request.user,
                **data,
            )
        except IdempotencyConflict as exc:
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)
        ingestion = (
            type(ingestion)
            .objects.select_related("test_run")
            .prefetch_related("test_run__run_cases")
            .get(id=ingestion.id)
        )
        return Response(
            serialize_ingestion_response(ingestion, replayed),
            status=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        )
