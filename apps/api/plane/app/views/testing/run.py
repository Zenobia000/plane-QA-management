# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db.models import Prefetch
from rest_framework import status
from rest_framework.response import Response

from plane.api.serializers.testing import AutomationIngestionSerializer
from plane.app.permissions import ProjectEntityPermission
from plane.app.serializers.testing import (
    TestDefectSerializer,
    TestDefectWriteSerializer,
    TestResultSerializer,
    TestResultWriteSerializer,
    TestRunSerializer,
    TestRunWriteSerializer,
)
from plane.app.views.base import BaseAPIView
from plane.db.models import TestResult, TestResultIssueLink, TestRun, TestRunCase
from plane.testing import (
    IdempotencyConflict,
    close_test_run,
    create_defect_from_result,
    create_fixed_test_run,
    ingest_automation_results,
    parse_junit_xml,
    record_test_result,
    serialize_ingestion_response,
)


def _run_queryset(*, slug, project_id):
    return (
        TestRun.objects.filter(workspace__slug=slug, project_id=project_id)
        .select_related("cycle", "module")
        .prefetch_related(
            Prefetch(
                "run_cases",
                queryset=TestRunCase.objects.select_related("test_case", "test_case_version").prefetch_related(
                    "test_case_version__steps",
                    Prefetch(
                        "results",
                        queryset=TestResult.objects.order_by("sequence").prefetch_related(
                            Prefetch("issue_links", queryset=TestResultIssueLink.objects.select_related("issue__state"))
                        ),
                    ),
                ),
            )
        )
    )


class TestRunListCreateEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        runs = _run_queryset(slug=slug, project_id=project_id)
        for field in ("status", "build", "cycle_id", "module_id", "run_type"):
            value = request.query_params.get(field)
            if value:
                runs = runs.filter(**{field: value})
        if request.query_params.get("per_page") or request.query_params.get("cursor"):
            return self.paginate(
                request=request,
                queryset=runs,
                order_by="-created_at",
                on_results=lambda items: TestRunSerializer(items, many=True).data,
                default_per_page=25,
                max_per_page=100,
            )
        return Response(TestRunSerializer(runs, many=True).data)

    def post(self, request, slug, project_id):
        serializer = TestRunWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        test_run = create_fixed_test_run(project_id=project_id, **serializer.validated_data)
        hydrated = _run_queryset(slug=slug, project_id=project_id).get(id=test_run.id)
        return Response(TestRunSerializer(hydrated).data, status=status.HTTP_201_CREATED)


class TestRunDetailEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id, test_run_id):
        test_run = _run_queryset(slug=slug, project_id=project_id).get(id=test_run_id)
        return Response(TestRunSerializer(test_run).data)


class TestRunResultEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def post(self, request, slug, project_id, test_run_id, run_case_id):
        run_case = TestRunCase.objects.get(id=run_case_id, test_run_id=test_run_id, project_id=project_id)
        serializer = TestResultWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = record_test_result(
            run_case_id=run_case.id,
            project_id=project_id,
            executed_by=request.user,
            **serializer.validated_data,
        )
        return Response(TestResultSerializer(result).data, status=status.HTTP_201_CREATED)


class TestRunCloseEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def post(self, request, slug, project_id, test_run_id):
        close_test_run(test_run_id=test_run_id, project_id=project_id)
        test_run = _run_queryset(slug=slug, project_id=project_id).get(id=test_run_id)
        return Response(TestRunSerializer(test_run).data)


class TestResultDefectEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def post(self, request, slug, project_id, test_run_id, run_case_id, result_id):
        result = TestResult.objects.get(
            id=result_id,
            run_case_id=run_case_id,
            run_case__test_run_id=test_run_id,
            project_id=project_id,
        )
        serializer = TestDefectWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        link = create_defect_from_result(
            result_id=result.id,
            run_case_id=run_case_id,
            project_id=project_id,
            created_by=request.user,
            **serializer.validated_data,
        )
        link = TestResultIssueLink.objects.select_related("issue__state").get(id=link.id)
        return Response(TestDefectSerializer(link).data, status=status.HTTP_201_CREATED)


class AppAutomationIngestionEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def post(self, request, slug, project_id):
        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        if not idempotency_key:
            return Response({"error": "Idempotency-Key header is required."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = AutomationIngestionSerializer(data=request.data)
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
        ingestion = type(ingestion).objects.select_related("test_run").prefetch_related("test_run__run_cases").get(
            id=ingestion.id
        )
        return Response(
            serialize_ingestion_response(ingestion, replayed),
            status=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        )
