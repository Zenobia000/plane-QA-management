# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""The shop-floor seed, end to end.

This seed had no test, which is how it came to build two sprints, two modules and seven
saved views that no sidebar could reach. It is also the only thing that exercises the whole
write path -- classification, breakdown, scheduling, contracts, a run, a defect loop -- so
running it is worth more than any single assertion below.

The state assertions are the reason this file exists now. Every item is placed by state
*name*; the seed previously addressed states by group, which was unambiguous only while a
project had one state per group.
"""

from io import StringIO

import pytest
from django.core.management import call_command

from plane.db.models import Issue, IssueView, Label, Project, State, TestResultIssueLink
from plane.db.models.state import SDLC_STATES, StateGroup


@pytest.fixture
def seeded(workspace):
    call_command("seed_testing_demo", workspace=workspace.slug, identifier="DEMO", stdout=StringIO())
    return Project.objects.get(workspace=workspace, identifier="DEMO")


@pytest.mark.unit
@pytest.mark.django_db
class TestSeededWorkflow:
    def test_project_carries_the_sdlc_states(self, seeded):
        expected = {s["name"] for s in SDLC_STATES if s["group"] != StateGroup.TRIAGE.value}
        assert set(seeded.project_state.values_list("name", flat=True)) == expected

    def test_work_items_land_in_the_states_the_seed_names(self, seeded):
        """A group-keyed lookup would put every started item in one arbitrary state."""
        by_name = {issue.name: issue.state.name for issue in Issue.issue_objects.filter(project=seeded)}

        assert by_name["客服以訂單編號查詢處理歷程"] == "Done"
        assert by_name["歷程匯出為對帳報表"] == "In Design"
        assert by_name["審核結果回寫金流系統"] == "Pending"
        assert by_name["使用者僅能存取授權區域訂單"] == "PR Reviewing"
        assert by_name["通知 5 秒內送達使用者"] == "In Diversity Testing"
        assert by_name["主管審核退貨紀錄"] == "Todo"

    def test_the_qa_handoff_is_spread_across_distinct_states(self, seeded):
        """The whole point: the board shows where work sits, not just "in progress"."""
        started = seeded.project_state.filter(group=StateGroup.STARTED.value)
        occupied = {
            issue.state.name
            for issue in Issue.issue_objects.filter(project=seeded, state__in=started).select_related("state")
        }
        assert len(occupied) >= 5

    def test_standing_work_is_a_label_not_a_state(self, seeded):
        """`Resident` in the reference design; a label here, so it distorts no burndown."""
        assert not State.objects.filter(project=seeded, name="Resident").exists()

        label = Label.objects.get(project=seeded, name="常駐維運")
        tagged = Issue.issue_objects.filter(project=seeded, label_issue__label=label)
        assert [issue.name for issue in tagged] == ["通知服務失敗率低於 0.5%"]


@pytest.mark.unit
@pytest.mark.django_db
class TestSeededDefectLoop:
    def test_the_resolved_defect_reaches_done(self, seeded):
        """`states["Done"]` by name. A group lookup could land it in any `started` state."""
        defect_ids = TestResultIssueLink.objects.filter(project=seeded).values_list("issue_id", flat=True)
        defects = Issue.objects.filter(id__in=defect_ids).select_related("state")

        assert defects.count() == 2
        assert {d.state.group for d in defects} == {"completed", "backlog"}

    def test_the_open_defect_still_blocks_the_gate(self, seeded):
        """A defect is open while its group is neither completed nor cancelled."""
        defect_ids = TestResultIssueLink.objects.filter(project=seeded).values_list("issue_id", flat=True)
        open_defects = Issue.objects.filter(id__in=defect_ids).exclude(state__group__in=("completed", "cancelled"))
        assert open_defects.count() == 1


@pytest.mark.unit
@pytest.mark.django_db
def test_seed_creates_the_saved_views_it_reports(seeded):
    """Six project views -- the seventh is workspace-scoped, so it has no project.

    The standup view groups by state, which only became worth reading once the project
    carried more than one started state.
    """
    views = IssueView.objects.filter(project=seeded)
    assert views.count() == 6
    standup = views.get(name="本期進行中")
    assert standup.display_filters["group_by"] == "state"
