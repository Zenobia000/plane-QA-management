# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from rest_framework import status

from plane.db.models import (
    Estimate,
    EstimatePoint,
    Issue,
    Project,
    ProjectMember,
    State,
    TestResultIssueLink,
)
from plane.testing import create_defect_from_result, create_fixed_test_run, create_test_case
from plane.testing import link_test_case_to_work_item, record_test_result


@pytest.fixture
def testing_project(db, workspace, create_user):
    project = Project.objects.create(
        name="Hierarchy Project",
        identifier="HIER",
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


@pytest.mark.contract
@pytest.mark.django_db
class TestEpicHierarchy:
    """Each level has to report what sits beneath it, or the tree is just indented noise."""

    def _url(self, workspace, project):
        return f"/api/workspaces/{workspace.slug}/projects/{project.id}/epic-hierarchy/"

    def _state(self, workspace, project, name, group):
        return State.objects.create(
            workspace=workspace, project=project, name=name, group=group, sequence=1000
        )

    def _tree(self, workspace, project):
        started = self._state(workspace, project, "In Progress", "started")
        done = self._state(workspace, project, "Done", "completed")
        epic = Issue.objects.create(workspace=workspace, project=project, name="Epic", state=started)
        feature = Issue.objects.create(
            workspace=workspace, project=project, name="Feature", state=started, parent=epic
        )
        return epic, feature, started, done

    def test_rollup_aggregates_state_and_points_across_every_depth(
        self, session_client, workspace, testing_project
    ):
        epic, feature, started, done = self._tree(workspace, testing_project)
        estimate = Estimate.objects.create(
            workspace=workspace, project=testing_project, name="Fibonacci", type="points"
        )
        # Keys are 1-based ordinals; the values are what a point total must sum.
        five = EstimatePoint.objects.create(
            estimate=estimate, workspace=workspace, project=testing_project, key=4, value="5"
        )
        eight = EstimatePoint.objects.create(
            estimate=estimate, workspace=workspace, project=testing_project, key=5, value="8"
        )
        Issue.objects.create(
            workspace=workspace, project=testing_project, name="Story A", state=done,
            parent=feature, estimate_point=five,
        )
        Issue.objects.create(
            workspace=workspace, project=testing_project, name="Story B", state=started,
            parent=feature, estimate_point=eight,
        )
        # Unsized work is counted rather than treated as zero, so a total is never
        # quietly understated.
        Issue.objects.create(
            workspace=workspace, project=testing_project, name="Story C", state=started, parent=feature
        )

        response = session_client.get(self._url(workspace, testing_project))
        assert response.status_code == status.HTTP_200_OK
        nodes = response.json()["nodes"]

        assert [node["name"] for node in nodes] == ["Epic"]
        epic_node = nodes[0]
        rollup = epic_node["rollup"]
        assert rollup["descendants"] == 4
        assert rollup["state_distribution"]["completed"] == 1
        assert rollup["state_distribution"]["started"] == 4
        # 5 + 8, and emphatically not 4 + 5 which is what summing the keys would give.
        assert rollup["points"] == {"total": 13, "sized": 2, "unsized": 3}
        assert epic_node["children"][0]["name"] == "Feature"
        assert epic_node["children"][0]["rollup"]["points"]["total"] == 13

    def test_coverage_and_worst_status_travel_up_from_the_story_that_owns_them(
        self, session_client, workspace, testing_project
    ):
        epic, feature, started, _done = self._tree(workspace, testing_project)
        covered = Issue.objects.create(
            workspace=workspace, project=testing_project, name="Covered", state=started, parent=feature
        )
        Issue.objects.create(
            workspace=workspace, project=testing_project, name="Uncovered", state=started, parent=feature
        )
        case = create_test_case(project_id=testing_project.id, title="Contract")
        link_test_case_to_work_item(
            test_case_id=case.id, issue_id=covered.id, project_id=testing_project.id
        )
        run = create_fixed_test_run(
            project_id=testing_project.id, name="Run", test_case_ids=[case.id], build="b1"
        )
        record_test_result(
            run_case_id=run.run_cases.first().id, project_id=testing_project.id,
            status="failed", actual_result={"text": "boom"},
        )

        nodes = session_client.get(self._url(workspace, testing_project)).json()["nodes"]
        rollup = nodes[0]["rollup"]["coverage"]

        # Four requirements are in scope. Three count as covered, because coverage is
        # inherited upward: the contract sits on one story, and the feature and epic that
        # deliver it are answered by it. Only the sibling story nothing verifies is
        # uncovered -- which is the number a delivery decision needs.
        assert rollup["in_scope"] == 4
        assert rollup["covered"] == 3
        assert rollup["uncovered"] == 1
        # The failure belongs to a story two levels down and still surfaces on the epic.
        assert rollup["latest_status"] == "failed"

    def test_defects_are_excluded_rather_than_rendered_as_roots(
        self, session_client, workspace, testing_project, create_user
    ):
        epic, feature, started, _done = self._tree(workspace, testing_project)
        story = Issue.objects.create(
            workspace=workspace, project=testing_project, name="Story", state=started, parent=feature
        )
        case = create_test_case(project_id=testing_project.id, title="Contract")
        link_test_case_to_work_item(
            test_case_id=case.id, issue_id=story.id, project_id=testing_project.id
        )
        run = create_fixed_test_run(
            project_id=testing_project.id, name="Run", test_case_ids=[case.id], build="b1"
        )
        run_case = run.run_cases.first()
        failure = record_test_result(
            run_case_id=run_case.id, project_id=testing_project.id, status="failed",
            actual_result={"text": "boom"},
        )
        create_defect_from_result(
            result_id=failure.id, run_case_id=run_case.id, project_id=testing_project.id,
            created_by=create_user,
        )
        assert TestResultIssueLink.objects.filter(project=testing_project).count() == 1

        nodes = session_client.get(self._url(workspace, testing_project)).json()["nodes"]

        # A defect has no parent, so leaving it in would put it beside the epic as a
        # second root and inflate every count above it.
        assert [node["name"] for node in nodes] == ["Epic"]
        assert nodes[0]["rollup"]["descendants"] == 2

    def test_non_member_cannot_read_the_hierarchy(self, api_client, workspace, testing_project):
        response = api_client.get(self._url(workspace, testing_project))
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
