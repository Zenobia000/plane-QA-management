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

from plane.db.models import Cycle, Issue, IssueView, Label, Project, State, TestResultIssueLink
from plane.db.models.state import SDLC_STATES, StateGroup
from plane.utils.analytics_plot import burndown_plot


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
class TestSeededBurndown:
    """The seed exists to be looked at, and a flat burndown shows nothing.

    `Issue.save()` stamps `completed_at` with the current time on entering a completed
    state, so every seeded delivery originally recorded as finishing the moment the seed
    ran -- days after the previous sprint had closed. `burndown_plot` only counts
    completions falling inside the sprint window, so the chart held flat at the opening
    total with every story marked done.
    """

    @staticmethod
    def _plot(cycle):
        cycle.total_issues = Issue.issue_objects.filter(
            issue_cycle__cycle_id=cycle.id, issue_cycle__deleted_at__isnull=True
        ).count()
        return burndown_plot(
            queryset=cycle,
            slug=cycle.workspace.slug,
            project_id=str(cycle.project_id),
            plot_type="issues",
            cycle_id=str(cycle.id),
        )

    def test_deliveries_are_dated_inside_the_sprint_that_delivered_them(self, seeded):
        for cycle in Cycle.objects.filter(project=seeded):
            delivered = Issue.issue_objects.filter(
                issue_cycle__cycle_id=cycle.id, completed_at__isnull=False
            )
            assert delivered.exists(), f"{cycle.name} delivered nothing"
            for issue in delivered:
                assert cycle.start_date <= issue.completed_at <= cycle.end_date, (
                    f"{issue.name} completed at {issue.completed_at}, outside {cycle.name}"
                )

    def test_the_closed_sprint_burns_all_the_way_down(self, seeded):
        cycle = Cycle.objects.get(project=seeded, name="Sprint 2026-07B")
        plotted = [v for v in self._plot(cycle).values() if v is not None]

        assert plotted[0] > plotted[-1], "burndown never descended"
        assert plotted[-1] == 0, "a fully delivered sprint should reach zero"

    def test_the_running_sprint_descends_without_reaching_zero(self, seeded):
        cycle = Cycle.objects.get(project=seeded, name="Sprint 2026-08A")
        chart = self._plot(cycle)
        plotted = [v for v in chart.values() if v is not None]

        assert plotted[0] > plotted[-1], "burndown never descended"
        assert plotted[-1] > 0, "a sprint still in flight should have work left"
        # Dates past today carry no reading at all, so the chart stops rather than
        # reporting the remaining work as delivered.
        assert any(v is None for v in chart.values())

    def test_burnup_is_the_complement_of_the_burndown(self, seeded):
        """What the CE burn-up chart derives client-side, checked against its source."""
        cycle = Cycle.objects.get(project=seeded, name="Sprint 2026-07B")
        total = Issue.issue_objects.filter(
            issue_cycle__cycle_id=cycle.id, issue_cycle__deleted_at__isnull=True
        ).count()
        burnup = [total - v for v in self._plot(cycle).values() if v is not None]

        assert burnup[0] < burnup[-1]
        assert burnup[-1] == total


@pytest.fixture
def eager_tasks():
    """Run queued Celery work in-process for the duration of one test.

    Soft deletion sweeps a row's children from a background task, so with no worker
    attached the purge below would look like it stranded everything it owns. Scoped to
    the test rather than the settings module, because the rest of the suite is written
    against tasks that do not run.
    """
    from plane.celery import app

    previous = app.conf.task_always_eager
    app.conf.task_always_eager = True
    yield
    app.conf.task_always_eager = previous


@pytest.mark.unit
@pytest.mark.django_db
def test_reseeding_strands_no_children(workspace, eager_tasks):
    """`purge()` must delete per instance; a queryset delete skips the cascade task.

    Bulk soft deletion is a plain `update(deleted_at=...)`, which never reaches
    `SoftDeleteModel.delete()` and so never queues the sweep of a project's cycles and
    work items. Re-running this seed used to leave both alive under a project the UI had
    already stopped showing.
    """
    call_command("seed_testing_demo", workspace=workspace.slug, identifier="DEMO", stdout=StringIO())
    call_command(
        "seed_testing_demo", workspace=workspace.slug, identifier="DEMO", force=True, stdout=StringIO()
    )

    dead = Project.all_objects.filter(workspace=workspace, identifier="DEMO", deleted_at__isnull=False)
    assert dead.exists(), "the first project should have been purged"

    assert not Cycle.objects.filter(project__in=dead).exists()
    assert not Issue.issue_objects.filter(project__in=dead).exists()


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
