# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from django.utils import timezone
from rest_framework import status

from plane.db.models import Issue, Project, ProjectMember, TestCase, TestResult, TestResultIssueLink, TestRun
from plane.testing import create_test_case, link_test_case_to_work_item, publish_test_case_version


@pytest.fixture
def testing_project(db, workspace, create_user):
    project = Project.objects.create(
        name="Execution Project",
        identifier="EXEC",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(
        workspace=workspace,
        project=project,
        member=create_user,
        role=20,
        is_active=True,
    )
    return project


def _runs_url(workspace, project):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/testing/test-runs/"


@pytest.mark.contract
@pytest.mark.django_db
class TestTestingRunsAPI:
    def test_fixed_run_pins_version_and_retest_appends_results(
        self, session_client, workspace, testing_project
    ):
        test_case = create_test_case(
            project_id=testing_project.id,
            title="Pinned version one",
            steps=[{"action": {"text": "Execute version one"}}],
        )

        created = session_client.post(
            _runs_url(workspace, testing_project),
            {
                "name": "Release smoke",
                "build": "1.0.0",
                "test_case_ids": [str(test_case.id)],
                "configuration": {"browser": "Chrome"},
            },
            format="json",
        )

        assert created.status_code == status.HTTP_201_CREATED
        run = created.json()
        run_case = run["run_cases"][0]
        assert run_case["test_case_version"]["version"] == 1
        assert run["progress"] == {
            "total": 1,
            "open": 1,
            "passed": 0,
            "failed": 0,
            "blocked": 0,
            "skipped": 0,
        }

        publish_test_case_version(
            test_case_id=test_case.id,
            project_id=testing_project.id,
            title="Library version two",
        )
        detail_url = f"{_runs_url(workspace, testing_project)}{run['id']}/"
        detail = session_client.get(detail_url).json()
        assert detail["run_cases"][0]["test_case_version"]["title"] == "Pinned version one"

        result_url = f"{detail_url}cases/{run_case['id']}/results/"
        failed = session_client.post(
            result_url,
            {"status": "failed", "actual_result": {"text": "Wrong response"}},
            format="json",
        )
        passed = session_client.post(result_url, {"status": "passed"}, format="json")
        assert failed.status_code == status.HTTP_201_CREATED
        assert passed.status_code == status.HTTP_201_CREATED
        assert [failed.json()["sequence"], passed.json()["sequence"]] == [1, 2]
        assert TestResult.objects.filter(run_case_id=run_case["id"]).count() == 2

        updated = session_client.get(detail_url).json()
        assert updated["run_cases"][0]["latest_status"] == "passed"
        assert updated["progress"]["passed"] == 1

    def test_completed_run_rejects_more_results(self, session_client, workspace, testing_project):
        test_case = create_test_case(project_id=testing_project.id, title="Close protection")
        run = session_client.post(
            _runs_url(workspace, testing_project),
            {"name": "Closable run", "test_case_ids": [str(test_case.id)]},
            format="json",
        ).json()
        detail_url = f"{_runs_url(workspace, testing_project)}{run['id']}/"

        closed = session_client.post(f"{detail_url}close/", {}, format="json")
        rejected = session_client.post(
            f"{detail_url}cases/{run['run_cases'][0]['id']}/results/",
            {"status": "passed"},
            format="json",
        )

        assert closed.status_code == status.HTTP_200_OK
        assert closed.json()["status"] == "completed"
        assert rejected.status_code == status.HTTP_400_BAD_REQUEST

    def test_failed_result_creates_traceable_plane_defect(self, session_client, workspace, testing_project):
        test_case = create_test_case(
            project_id=testing_project.id,
            title="Checkout error is explained",
            preconditions={"text": "Signed in with a stocked cart"},
            steps=[{"action": {"text": "Submit checkout"}, "expected_result": {"text": "Order created"}}],
        )
        run = session_client.post(
            _runs_url(workspace, testing_project),
            {
                "name": "Defect run",
                "build": "2026.07.14",
                "configuration": {"browser": "Chromium", "region": "local"},
                "test_case_ids": [str(test_case.id)],
            },
            format="json",
        ).json()
        run_case = run["run_cases"][0]
        result_url = f"{_runs_url(workspace, testing_project)}{run['id']}/cases/{run_case['id']}/results/"
        result = session_client.post(
            result_url,
            {"status": "failed", "actual_result": {"text": "HTTP 500"}},
            format="json",
        ).json()

        created = session_client.post(f"{result_url}{result['id']}/defects/", {}, format="json")

        assert created.status_code == status.HTTP_201_CREATED
        defect = created.json()
        assert defect["name"] == "[TC-1] Checkout error is explained"
        issue = Issue.objects.get(id=defect["id"], project=testing_project)
        assert "Chromium" in issue.description_html
        assert "Signed in with a stocked cart" in issue.description_html
        assert "Submit checkout" in issue.description_html
        assert "Expected:</strong> Order created" in issue.description_html
        assert "HTTP 500" in issue.description_html
        assert f'/{workspace.slug}/projects/{testing_project.id}/testing' in issue.description_html
        assert issue.description_json["environment"] == {"browser": "Chromium", "region": "local"}
        assert issue.description_json["source_url"].endswith(
            f"/{workspace.slug}/projects/{testing_project.id}/testing"
        )
        assert TestResultIssueLink.objects.filter(test_result_id=result["id"], issue_id=defect["id"]).exists()
        detail = session_client.get(f"{_runs_url(workspace, testing_project)}{run['id']}/").json()
        assert detail["run_cases"][0]["results"][0]["defects"][0]["id"] == defect["id"]

        # A soft-deleted run's related rows can remain visible until the asynchronous
        # deletion task catches up; reporting must not count that stale defect.
        TestRun.all_objects.filter(id=run["id"]).update(deleted_at=timezone.now())
        overview = session_client.get(
            f"/api/workspaces/{workspace.slug}/projects/{testing_project.id}/testing/overview/"
        ).json()
        assert overview["open_defects"] == 0

    def test_overview_explains_release_blockers(self, session_client, workspace, testing_project):
        test_case = create_test_case(project_id=testing_project.id, title="Release smoke")
        covered = Issue.objects.create(workspace=workspace, project=testing_project, name="Covered requirement")
        uncovered = Issue.objects.create(workspace=workspace, project=testing_project, name="Uncovered requirement")
        link_test_case_to_work_item(
            test_case_id=test_case.id, issue_id=covered.id, project_id=testing_project.id
        )
        run = session_client.post(
            _runs_url(workspace, testing_project),
            {"name": "Release candidate", "test_case_ids": [str(test_case.id)]},
            format="json",
        ).json()
        session_client.post(
            f"{_runs_url(workspace, testing_project)}{run['id']}/cases/{run['run_cases'][0]['id']}/results/",
            {"status": "failed"},
            format="json",
        )

        overview = session_client.get(
            f"/api/workspaces/{workspace.slug}/projects/{testing_project.id}/testing/overview/"
        )

        assert overview.status_code == status.HTTP_200_OK
        assert overview.json()["latest_run"]["failed"] == 1
        assert overview.json()["release_gate"]["ready"] is False
        assert "failed test case" in overview.json()["release_gate"]["blockers"][0]
        assert overview.json()["scorecards"][0]["failed"] == 1

        coverage = session_client.get(
            f"/api/workspaces/{workspace.slug}/projects/{testing_project.id}/testing/requirement-coverage/"
        )
        assert coverage.status_code == status.HTTP_200_OK
        assert coverage.json()["covered"] == 1
        assert coverage.json()["uncovered"] == 1
        rows = {row["work_item_id"]: row for row in coverage.json()["work_items"]}
        assert rows[str(covered.id)]["latest_status"] == "failed"
        assert rows[str(uncovered.id)]["latest_status"] is None

        # Requirement links from a soft-deleted case must not inflate coverage while
        # asynchronous related-object cleanup is pending.
        TestCase.all_objects.filter(id=test_case.id).update(deleted_at=timezone.now())
        coverage = session_client.get(
            f"/api/workspaces/{workspace.slug}/projects/{testing_project.id}/testing/requirement-coverage/"
        ).json()
        assert coverage["covered"] == 0
        assert coverage["uncovered"] == 2
