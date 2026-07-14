# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from rest_framework import status
from rest_framework.response import Response

from plane.api.serializers.testing import AutomationIngestionSerializer
from plane.app.permissions import ProjectEntityPermission
from plane.testing import IdempotencyConflict, ingest_automation_results, parse_junit_xml

from .base import BaseAPIView


def ingestion_response(ingestion, replayed):
    run = ingestion.test_run
    counts = {"passed": 0, "failed": 0, "blocked": 0, "skipped": 0, "open": 0}
    for run_case in run.run_cases.all():
        counts[run_case.latest_status] += 1
    return {
        "id": str(ingestion.id),
        "idempotency_key": ingestion.idempotency_key,
        "replayed": replayed,
        "test_run": {"id": str(run.id), "name": run.name, "status": run.status, **counts},
        "diagnostics": ingestion.diagnostics,
    }


class AutomationIngestionEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]
    serializer_class = AutomationIngestionSerializer

    def post(self, request, slug, project_id):
        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        if not idempotency_key:
            return Response(
                {"error": "Idempotency-Key header is required."}, status=status.HTTP_400_BAD_REQUEST
            )
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
        ingestion = type(ingestion).objects.select_related("test_run").prefetch_related(
            "test_run__run_cases"
        ).get(id=ingestion.id)
        return Response(
            ingestion_response(ingestion, replayed),
            status=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        )
