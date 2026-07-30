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


class HierarchyFixtures:
    """URLs and the two-level skeleton both hierarchy suites build on."""

    def _url(self, workspace, project):
        return f"/api/workspaces/{workspace.slug}/projects/{project.id}/epic-hierarchy/"

    def _roots_url(self, workspace, project):
        return f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-item-hierarchy/"

    def _item_url(self, workspace, project, issue_id):
        return (
            f"/api/workspaces/{workspace.slug}/projects/{project.id}"
            f"/work-items/{issue_id}/hierarchy/"
        )

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


@pytest.mark.contract
@pytest.mark.django_db
class TestEpicHierarchy(HierarchyFixtures):
    """Each level has to report what sits beneath it, or the tree is just indented noise."""

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
        # Four items sit beneath the epic, but only the three stories are leaves. The
        # feature is a summary of those stories, so counting it too would state the same
        # work twice.
        assert rollup["descendants"] == 4
        assert rollup["leaves"] == 3
        assert sum(rollup["state_distribution"].values()) == 3
        assert rollup["state_distribution"]["completed"] == 1
        assert rollup["state_distribution"]["started"] == 2
        # 5 + 8, and emphatically not 4 + 5 which is what summing the keys would give.
        # Only Story C is unsized; the epic and the feature are not work awaiting an
        # estimate, they are nodes that aggregate one.
        assert rollup["points"] == {"total": 13, "sized": 2, "unsized": 1}
        assert epic_node["children"][0]["name"] == "Feature"
        assert epic_node["children"][0]["rollup"]["points"]["total"] == 13

    def test_a_parents_own_estimate_is_superseded_by_its_breakdown(
        self, session_client, workspace, testing_project
    ):
        """Estimating an epic and then breaking it down must not add the two together."""
        epic, feature, started, _done = self._tree(workspace, testing_project)
        estimate = Estimate.objects.create(
            workspace=workspace, project=testing_project, name="Fibonacci", type="points"
        )
        twenty = EstimatePoint.objects.create(
            estimate=estimate, workspace=workspace, project=testing_project, key=7, value="20"
        )
        five = EstimatePoint.objects.create(
            estimate=estimate, workspace=workspace, project=testing_project, key=4, value="5"
        )
        Issue.objects.filter(id=epic.id).update(estimate_point=twenty)
        Issue.objects.create(
            workspace=workspace, project=testing_project, name="Story", state=started,
            parent=feature, estimate_point=five,
        )

        nodes = session_client.get(self._url(workspace, testing_project)).json()["nodes"]

        # The epic's own 20 points are a pre-breakdown guess the stories replaced.
        assert nodes[0]["estimate_point"] == 20
        assert nodes[0]["rollup"]["points"]["total"] == 5

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

        # Two leaf stories are in scope; one holds a contract. The epic and feature are
        # also "covered" in their own right, because coverage is inherited upward -- but
        # that verdict is a restatement of the story beneath them, so counting it here
        # would inflate both sides of the ratio.
        assert rollup["in_scope"] == 2
        assert rollup["covered"] == 1
        assert rollup["uncovered"] == 1
        # The node's own inherited verdict is still reported, separately from the rollup.
        assert nodes[0]["covered"] is True
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
        assert nodes[0]["rollup"]["leaves"] == 1

    def test_a_feature_whose_stories_all_lack_contracts_counts_the_stories_only(
        self, session_client, workspace, testing_project
    ):
        """The case that exposed the double count: two gaps must not report as three."""
        epic, feature, started, _done = self._tree(workspace, testing_project)
        for name in ("Story A", "Story B"):
            Issue.objects.create(
                workspace=workspace, project=testing_project, name=name, state=started, parent=feature
            )

        nodes = session_client.get(self._url(workspace, testing_project)).json()["nodes"]
        coverage = nodes[0]["rollup"]["coverage"]

        # The feature is uncovered too, since nothing beneath it is verified. Counting it
        # alongside its own stories reported three missing contracts where two exist.
        assert coverage["in_scope"] == 2
        assert coverage["uncovered"] == 2

    def test_non_member_cannot_read_the_hierarchy(self, api_client, workspace, testing_project):
        response = api_client.get(self._url(workspace, testing_project))
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


@pytest.mark.contract
@pytest.mark.django_db
class TestWorkItemSubtreeHierarchy(HierarchyFixtures):
    """The same computation, asked of one node instead of every root."""

    def test_a_subtree_reports_what_the_full_tree_reported_for_that_node(
        self, session_client, workspace, testing_project
    ):
        epic, feature, started, _done = self._tree(workspace, testing_project)
        for name in ("Story A", "Story B"):
            Issue.objects.create(
                workspace=workspace, project=testing_project, name=name, state=started, parent=feature
            )

        from_root = session_client.get(self._roots_url(workspace, testing_project)).json()["nodes"]
        from_feature = session_client.get(
            self._item_url(workspace, testing_project, feature.id)
        ).json()["nodes"]

        # A feature is not an epic and has never needed a second endpoint to say so.
        assert [node["name"] for node in from_feature] == ["Feature"]
        assert from_feature[0] == from_root[0]["children"][0]
        assert from_feature[0]["rollup"]["leaves"] == 2

    def test_a_leaf_is_a_legitimate_subject_and_reports_an_empty_rollup(
        self, session_client, workspace, testing_project
    ):
        _epic, feature, started, _done = self._tree(workspace, testing_project)
        story = Issue.objects.create(
            workspace=workspace, project=testing_project, name="Story", state=started, parent=feature
        )

        nodes = session_client.get(self._item_url(workspace, testing_project, story.id)).json()["nodes"]

        # A leaf summarises nothing, so its rollup is empty by construction rather than by
        # special case -- the numbers it produces belong to its ancestors.
        assert nodes[0]["is_leaf"] is True
        assert nodes[0]["rollup"]["leaves"] == 0
        assert nodes[0]["rollup"]["descendants"] == 0

    def test_the_epic_alias_answers_identically_to_the_rootless_url(
        self, session_client, workspace, testing_project
    ):
        _epic, feature, started, _done = self._tree(workspace, testing_project)
        Issue.objects.create(
            workspace=workspace, project=testing_project, name="Story", state=started, parent=feature
        )

        legacy = session_client.get(self._url(workspace, testing_project))
        current = session_client.get(self._roots_url(workspace, testing_project))

        assert legacy.status_code == status.HTTP_200_OK
        assert legacy.json() == current.json()

    def test_a_defect_is_absent_from_the_hierarchy_rather_than_an_empty_subtree(
        self, session_client, workspace, testing_project, create_user
    ):
        _epic, feature, started, _done = self._tree(workspace, testing_project)
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
        # The factory returns the result-to-issue link, so the defect is its `issue_id`.
        defect_link = create_defect_from_result(
            result_id=failure.id, run_case_id=run_case.id, project_id=testing_project.id,
            created_by=create_user,
        )

        response = session_client.get(
            self._item_url(workspace, testing_project, defect_link.issue_id)
        )

        # Defects are evidence, not requirements. The tree excludes them, so asking one for
        # its rollup has to say "not here" rather than hand back a hollow node that would
        # read as "verified nothing".
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_a_work_item_from_another_project_is_not_reachable(
        self, session_client, workspace, testing_project, create_user
    ):
        other = Project.objects.create(
            name="Other", identifier="OTHR", workspace=workspace, created_by=create_user
        )
        ProjectMember.objects.create(
            workspace=workspace, project=other, member=create_user, role=20, is_active=True
        )
        elsewhere = Issue.objects.create(workspace=workspace, project=other, name="Elsewhere")

        response = session_client.get(self._item_url(workspace, testing_project, elsewhere.id))

        assert response.status_code == status.HTTP_404_NOT_FOUND
