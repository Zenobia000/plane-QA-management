# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from collections import defaultdict

from django.db.models import Count, Prefetch, Q
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ProjectEntityPermission
from plane.app.views.base import BaseAPIView
from plane.app.serializers.testing import ReleaseEvidenceSerializer, ReleaseEvidenceWriteSerializer
from plane.db.models import (
    Issue,
    Project,
    ReleaseEvidence,
    TestCase,
    TestCaseWorkItemLink,
    TestResultIssueLink,
    TestRun,
    TestRunCase,
)

# Nobody has scheduled a backlog item yet, and a cancelled one will never ship,
# so neither is expected to carry an acceptance contract. Everything else is in
# scope: Definition of Ready asks for the contract before implementation starts,
# not after it finishes.
UNSCHEDULED_STATE_GROUPS = {"backlog", "cancelled"}

# Worst status wins when several contracts answer for one requirement.
STATUS_PRECEDENCE = {"failed": 0, "blocked": 1, "open": 2, "skipped": 3, "passed": 4}


def _status_counts(run):
    counts = {status: 0 for status, _label in TestRunCase.STATUS_CHOICES}
    counts.update(
        {
            item["latest_status"]: item["count"]
            for item in run.run_cases.values("latest_status").annotate(count=Count("id"))
        }
    )
    return counts


def _latest_status(test_case):
    latest_run_case = max(
        test_case.run_cases.all(),
        key=lambda item: item.test_run.created_at,
        default=None,
    )
    return latest_run_case.latest_status if latest_run_case else "open"


def requirement_coverage(project_id):
    """Coverage per requirement, rolled up through the work-item hierarchy.

    Contracts attach where acceptance is decided -- at story level -- so a feature
    or epic reading its own links alone would always look untested. Each row
    therefore reports the contracts beneath it as well as its own.

    Only types marked `needs_acceptance` produce rows. An implementation task is how
    something gets built, not something the product promises, so nothing is owed an
    acceptance test for it -- the story above it carries that. Counting them buried the
    signal: eight uncovered rows on the authors' own instance, of which one was a real
    gap. Their contracts still roll up, because `inherited` walks children regardless of
    whether the child earns a row of its own.

    Work items with no type at all are kept. A project that never adopted types would
    otherwise report nothing, and silence is the one answer a coverage report must not give.

    Defects are excluded before anything is counted, and this stays even though defects are
    typed `Bug` and `Bug` is not a requirement type. The two rules catch different things:
    the type says what a row is *for*, the link says where it *came from*, and a defect
    filed under some other type is still evidence rather than a promise.

    A row that summarises other counted rows does not count toward the totals -- see
    `counts_toward_coverage`. Acceptance is agreed at the level where the work is specified;
    an epic is covered exactly when its stories are, so counting it again adds a second vote
    for the same decision. On this instance six epics and features held no contract of their
    own and contributed six to the numerator, turning 90% coverage into 94%. They keep their
    rows, because seeing which epic contains the gap is the reason the roll-up exists.

    A summary is derived from the tree rather than declared, so it needs no configuration and
    self-corrects: an epic with nothing beneath it summarises nothing, counts for itself, and
    is reported uncovered -- which is right, since it is a promise with no acceptance anywhere.
    """
    active_links = (
        TestCaseWorkItemLink.objects.filter(
            deleted_at__isnull=True,
            test_case__deleted_at__isnull=True,
            test_case__archived_at__isnull=True,
        )
        .select_related("test_case")
        .prefetch_related("test_case__run_cases__test_run")
    )
    issues = list(
        Issue.issue_objects.filter(project_id=project_id)
        .select_related("state", "type")
        .prefetch_related(Prefetch("test_case_links", queryset=active_links))
    )
    defect_ids = set(
        TestResultIssueLink.objects.filter(
            project_id=project_id,
            test_result__deleted_at__isnull=True,
            test_result__run_case__deleted_at__isnull=True,
            test_result__run_case__test_run__deleted_at__isnull=True,
        ).values_list("issue_id", flat=True)
    )

    own_cases = {issue.id: [link.test_case for link in issue.test_case_links.all()] for issue in issues}
    children = defaultdict(list)
    for issue in issues:
        if issue.parent_id:
            children[issue.parent_id].append(issue.id)

    def inherited(issue_id, seen):
        # `seen` also guards against a parent cycle the database does not forbid.
        if issue_id in seen:
            return []
        seen.add(issue_id)
        collected = list(own_cases.get(issue_id, []))
        for child_id in children.get(issue_id, []):
            collected.extend(inherited(child_id, seen))
        return collected

    def counted(issue):
        # Untyped is not a statement that this is not a requirement, so it stays.
        return issue.id not in defect_ids and (not issue.type_id or issue.type.needs_acceptance)

    counted_ids = {issue.id for issue in issues if counted(issue)}
    parent_of = {issue.id: issue.parent_id for issue in issues}
    # Anything with a counted row beneath it is a summary of that row, at any depth -- a
    # story under a task under an epic still makes the epic a summary.
    summary_ids = set()
    for issue_id in counted_ids:
        walked = {issue_id}
        ancestor = parent_of.get(issue_id)
        while ancestor and ancestor not in walked:
            walked.add(ancestor)
            if ancestor in counted_ids:
                summary_ids.add(ancestor)
            ancestor = parent_of.get(ancestor)

    rows = []
    for issue in issues:
        if not counted(issue):
            continue
        own = own_cases.get(issue.id, [])
        effective = {case.id: case for case in inherited(issue.id, set())}.values()
        statuses = [_latest_status(case) for case in effective]
        state_group = issue.state.group if issue.state else None
        rows.append(
            {
                "work_item_id": str(issue.id),
                "sequence_id": issue.sequence_id,
                "name": issue.name,
                "state_group": state_group,
                "parent_id": str(issue.parent_id) if issue.parent_id else None,
                "covered": bool(effective),
                "covered_directly": bool(own),
                # False for a row that only summarises others. Kept in the list so the tree
                # still shows where a gap sits; kept out of the totals so it is not a second
                # vote on the same acceptance decision.
                "counts_toward_coverage": issue.id not in summary_ids,
                "requires_contract": state_group not in UNSCHEDULED_STATE_GROUPS,
                "own_test_case_ids": [str(case.id) for case in own],
                "test_case_ids": [str(case.id) for case in effective],
                "latest_status": min(statuses, key=STATUS_PRECEDENCE.get) if statuses else None,
            }
        )
    return rows


def _counting(rows):
    """The rows the totals are entitled to use: leaves of the counted tree.

    A summary row is real and stays in the list, but it holds no acceptance decision of its
    own, so adding it to the numerator and the denominator states the same fact twice.
    """
    return [row for row in rows if row["counts_toward_coverage"]]


def _uncovered_in_scope(rows):
    return [row for row in _counting(rows) if row["requires_contract"] and not row["covered"]]


class TestingOverviewEndpoint(BaseAPIView):
    """Project quality snapshot using explicit latest-result and coverage definitions."""

    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        cases = TestCase.objects.filter(project_id=project_id, archived_at__isnull=True)
        case_total = cases.count()
        linked_cases = cases.filter(work_item_links__isnull=False).distinct().count()
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

        rows = requirement_coverage(project_id)
        in_scope = [row for row in _counting(rows) if row["requires_contract"]]
        covered_requirements = sum(1 for row in in_scope if row["covered"])
        uncovered = _uncovered_in_scope(rows)

        blockers = []
        if status_counts["failed"]:
            blockers.append(f'{status_counts["failed"]} failed test case(s) in the latest run')
        if status_counts["blocked"]:
            blockers.append(f'{status_counts["blocked"]} blocked test case(s) in the latest run')
        if open_defects:
            blockers.append(f"{open_defects} open defect(s)")
        if status_counts["open"]:
            blockers.append(f'{status_counts["open"]} unexecuted test case(s) in the latest run')
        # Shipping a scheduled requirement that nothing verifies is the failure
        # Definition of Ready exists to prevent, so the gate has to see it.
        if uncovered:
            blockers.append(f"{len(uncovered)} scheduled requirement(s) with no acceptance contract")
        # Availability, scans and sign-offs are not produced by running tests, but a
        # release decision rests on them just the same.
        evidence = list(ReleaseEvidence.objects.filter(project_id=project_id))
        for item in evidence:
            if item.status == "failing":
                blockers.append(f"{item.name} is failing")
            elif item.status == "pending":
                blockers.append(f"{item.name} has not been recorded yet")

        return Response(
            {
                "library": {
                    "total": case_total,
                    "requirement_linked": linked_cases,
                    # How tidy the library is: the share of cases that answer for a
                    # requirement. Distinct from requirement coverage below, which is
                    # what a delivery decision actually rests on.
                    "linked_percent": round(linked_cases * 100 / case_total, 1) if case_total else 0,
                },
                "requirements": {
                    "total": len(in_scope),
                    "covered": covered_requirements,
                    "uncovered": len(uncovered),
                    "coverage_percent": (
                        round(covered_requirements * 100 / len(in_scope), 1) if in_scope else 0
                    ),
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
                "release_evidence": ReleaseEvidenceSerializer(evidence, many=True).data,
                "release_gate": {"ready": bool(latest_run) and not blockers, "blockers": blockers},
            }
        )


class TestingRequirementCoverageEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        rows = requirement_coverage(project_id)
        counting = _counting(rows)
        in_scope = [row for row in counting if row["requires_contract"]]
        return Response(
            {
                "total": len(counting),
                "covered": sum(1 for row in counting if row["covered"]),
                "uncovered": sum(1 for row in counting if not row["covered"]),
                "in_scope": len(in_scope),
                "uncovered_in_scope": len(_uncovered_in_scope(rows)),
                "work_items": rows,
            }
        )


class TestingReleaseEvidenceEndpoint(BaseAPIView):
    """External evidence a release gate consults but testing does not produce."""

    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        evidence = ReleaseEvidence.objects.filter(project_id=project_id)
        return Response(ReleaseEvidenceSerializer(evidence, many=True).data)

    def put(self, request, slug, project_id):
        serializer = ReleaseEvidenceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        # Upsert on the project-scoped key so a pipeline reporting the same check
        # repeatedly updates one row instead of growing the gate a duplicate each run.
        project = Project.objects.get(id=project_id)
        evidence, _ = ReleaseEvidence.objects.update_or_create(
            project_id=project_id,
            key=payload["key"],
            defaults={
                "workspace_id": project.workspace_id,
                "kind": payload["kind"],
                "name": payload["name"],
                "status": payload["status"],
                "detail": payload["detail"],
                "source_url": payload["source_url"],
            },
        )
        return Response(ReleaseEvidenceSerializer(evidence).data, status=status.HTTP_200_OK)

    def delete(self, request, slug, project_id):
        key = request.query_params.get("key")
        if not key:
            return Response({"error": "A key is required."}, status=status.HTTP_400_BAD_REQUEST)
        ReleaseEvidence.objects.filter(project_id=project_id, key=key).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
