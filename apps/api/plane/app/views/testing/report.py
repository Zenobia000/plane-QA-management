# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.db.models import Count, Prefetch, Q
from rest_framework.response import Response

from plane.app.permissions import ProjectEntityPermission
from plane.app.views.base import BaseAPIView
from plane.db.models import Issue, TestCase, TestCaseWorkItemLink, TestResultIssueLink, TestRun, TestRunCase


def _status_counts(run):
    counts = {status: 0 for status, _label in TestRunCase.STATUS_CHOICES}
    counts.update(
        {
            item["latest_status"]: item["count"]
            for item in run.run_cases.values("latest_status").annotate(count=Count("id"))
        }
    )
    return counts


class TestingOverviewEndpoint(BaseAPIView):
    """Project quality snapshot using explicit latest-result and coverage definitions."""

    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        cases = TestCase.objects.filter(project_id=project_id, archived_at__isnull=True)
        case_total = cases.count()
        covered_cases = cases.filter(work_item_links__isnull=False).distinct().count()
        runs = TestRun.objects.filter(project_id=project_id)
        latest_run = runs.prefetch_related("run_cases").first()
        status_counts = (
            _status_counts(latest_run)
            if latest_run
            else {status: 0 for status, _ in TestRunCase.STATUS_CHOICES}
        )
        open_defects = (
            TestResultIssueLink.objects.filter(
                project_id=project_id,
                test_result__deleted_at__isnull=True,
                test_result__run_case__deleted_at__isnull=True,
                test_result__run_case__test_run__deleted_at__isnull=True,
            )
            .exclude(Q(issue__state__group="completed") | Q(issue__state__group="cancelled"))
            .count()
        )
        blockers = []
        if status_counts["failed"]:
            blockers.append(f'{status_counts["failed"]} failed test case(s) in the latest run')
        if status_counts["blocked"]:
            blockers.append(f'{status_counts["blocked"]} blocked test case(s) in the latest run')
        if open_defects:
            blockers.append(f"{open_defects} open defect(s)")
        if status_counts["open"]:
            blockers.append(f'{status_counts["open"]} unexecuted test case(s) in the latest run')
        return Response(
            {
                "library": {
                    "total": case_total,
                    "requirement_linked": covered_cases,
                    "coverage_percent": round(covered_cases * 100 / case_total, 1) if case_total else 0,
                },
                "runs": {"total": runs.count(), "active": runs.filter(status="active").count()},
                "latest_run": (
                    {"id": str(latest_run.id), "name": latest_run.name, "status": latest_run.status, **status_counts}
                    if latest_run
                    else None
                ),
                "open_defects": open_defects,
                "scorecards": [
                    {
                        "id": str(run.id),
                        "name": run.name,
                        "build": run.build,
                        "configuration": run.configuration,
                        "status": run.status,
                        **_status_counts(run),
                    }
                    for run in runs.prefetch_related("run_cases")[:10]
                ],
                "release_gate": {"ready": bool(latest_run) and not blockers, "blockers": blockers},
            }
        )


class TestingRequirementCoverageEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        active_links = TestCaseWorkItemLink.objects.filter(
            deleted_at__isnull=True,
            test_case__deleted_at__isnull=True,
            test_case__archived_at__isnull=True,
        ).select_related("test_case").prefetch_related("test_case__run_cases")
        issues = Issue.issue_objects.filter(project_id=project_id).select_related("state").prefetch_related(
            Prefetch("test_case_links", queryset=active_links)
        )
        rows = []
        precedence = {"failed": 0, "blocked": 1, "open": 2, "skipped": 3, "passed": 4}
        for issue in issues:
            case_ids = []
            statuses = []
            for link in issue.test_case_links.all():
                case_ids.append(str(link.test_case_id))
                latest_run_case = max(
                    link.test_case.run_cases.all(),
                    key=lambda item: item.test_run.created_at,
                    default=None,
                )
                statuses.append(latest_run_case.latest_status if latest_run_case else "open")
            rows.append(
                {
                    "work_item_id": str(issue.id),
                    "sequence_id": issue.sequence_id,
                    "name": issue.name,
                    "state_group": issue.state.group if issue.state else None,
                    "covered": bool(case_ids),
                    "test_case_ids": case_ids,
                    "latest_status": min(statuses, key=precedence.get) if statuses else None,
                }
            )
        return Response(
            {
                "total": len(rows),
                "covered": sum(1 for row in rows if row["covered"]),
                "uncovered": sum(1 for row in rows if not row["covered"]),
                "work_items": rows,
            }
        )
