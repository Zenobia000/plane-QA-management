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

import re
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from plane.db.models import (
    Cycle,
    IssueRelation,
    IssueType,
    ReleaseEvidence,
    Page,
    EntityUpdate,
    EntityUpdateLabel,
    IntakeIssue,
    Issue,
    IssueView,
    Label,
    Project,
    State,
    TestResultIssueLink,
    WorkItemProperty,
    WorkItemPropertyValue,
)
from plane.db.models import TestCase as Case
from plane.db.models import TestFolder as Folder
from plane.db.models import TestCaseAutomationLink as AutomationLink
from plane.db.models import TestRun as Run
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


@pytest.mark.unit
@pytest.mark.django_db
class TestSeededEpicLayer:
    """What the Epics page needs from the seed, stated as assertions.

    The page is the work-item list scoped to `type__is_epic`, plus a per-epic progress bar
    computed from descendants. Everything it can show therefore depends on the epics
    differing from each other, and on at least one of them having work beneath it in every
    state group. The seed carried two epics that were identical on every axis the page
    groups by, so the list looked like a feature nobody had finished.
    """

    @staticmethod
    def _epics(project):
        return Issue.issue_objects.filter(project=project, type__is_epic=True).select_related("state")

    @staticmethod
    def _descendant_groups(epic):
        """State groups beneath one epic, walked the way `EpicAnalyticsEndpoint` walks it.

        To the bottom of the subtree, excluding the epic itself: an epic's children are
        features, and a feature's state says nothing about the stories under it.
        """
        groups = []
        frontier = [epic.id]
        while frontier:
            children = Issue.issue_objects.filter(parent_id__in=frontier).select_related("state")
            frontier = [child.id for child in children]
            groups.extend(child.state.group for child in children)
        return groups

    def test_the_epics_list_has_something_to_group(self, seeded):
        epics = self._epics(seeded)

        assert epics.count() >= 5
        assert len({epic.state.group for epic in epics}) >= 4
        assert len({epic.priority for epic in epics}) >= 4

    def test_every_epic_but_the_unplanned_one_carries_a_window(self, seeded):
        """Gantt and calendar place a row by its dates, and an epic joins no sprint.

        Most items take their window from the cycle they sit in. An epic spans sprints and
        belongs to none, so a dateless epic is simply absent from two of the five layouts.
        The backlog epic is the deliberate exception -- nothing has been committed for it.
        """
        dated = [epic for epic in self._epics(seeded) if epic.start_date and epic.target_date]

        assert len(dated) >= 4
        for epic in dated:
            assert epic.start_date <= epic.target_date, f"{epic.name} ends before it starts"

    def test_one_epic_reports_every_state_group_beneath_it(self, seeded):
        """A bar showing two of five segments cannot say whether the rest are unsupported."""
        spreads = [set(self._descendant_groups(epic)) for epic in self._epics(seeded)]

        assert any(len(spread) == 5 for spread in spreads), (
            f"no epic covers all five state groups; widest was {max(spreads, key=len)}"
        )

    def test_a_cancelled_epic_keeps_cancelled_work_in_its_denominator(self, seeded):
        """`EpicProgressSection` counts cancelled work rather than hiding it.

        Dropping it from the denominator would make a mostly-cancelled epic read as nearly
        complete. Nothing proved that until the seed had a cancelled epic to read.
        """
        cancelled = [epic for epic in self._epics(seeded) if epic.state.group == "cancelled"]

        assert cancelled, "no cancelled epic to read"
        groups = self._descendant_groups(cancelled[0])
        assert groups and set(groups) == {"cancelled"}

    def test_an_epic_with_no_descendants_exists(self, seeded):
        """`total === 0` hides the progress section, rather than drawing a zeroed bar."""
        childless = [epic for epic in self._epics(seeded) if not self._descendant_groups(epic)]

        assert childless, "every epic has work beneath it, so the empty case is never rendered"

    def test_exactly_the_open_overdue_work_is_countable(self, seeded):
        """Overdue means open and past target; finished-late is neither missed nor red."""
        today = timezone.now().date()
        overdue = Issue.issue_objects.filter(
            project=seeded, target_date__lt=today, state__group__in=("backlog", "unstarted", "started")
        )

        assert overdue.exists(), "no descendant is overdue, so the count never renders"

    def test_the_project_exposes_the_axes_it_uses(self, seeded):
        """Every item here is typed and the sidebar entry is what the epics live behind."""
        assert seeded.is_issue_type_enabled is True
        assert seeded.is_epic_enabled is True


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


@pytest.mark.unit
@pytest.mark.django_db
class TestSeededFrontline:
    """The overview's newest panels are invisible until someone has used them.

    A project with no intake shows no frontline panel and a project with no announcements
    shows an empty board -- correct in production, useless in a demo. These assertions say
    the seed leaves enough behind for both to render something, and that the field reports
    are not all in one triage state, which would make the panel look like a queue nobody
    has touched.
    """

    def test_the_grouping_dimension_is_marked_and_is_the_only_one(self, seeded):
        dimensions = WorkItemProperty.objects.filter(project=seeded, is_grouping_dimension=True)

        assert dimensions.count() == 1
        assert dimensions.first().kind == WorkItemProperty.Kind.MULTI_SELECT

    def test_field_reports_cover_every_triage_answer(self, seeded):
        """One uniform status would demo a queue, not a triage surface."""
        statuses = set(IntakeIssue.objects.filter(project=seeded).values_list("status", flat=True))

        assert {-2, 1, -1} <= statuses

    def test_every_report_is_attributed(self, seeded):
        reports = IntakeIssue.objects.filter(project=seeded)
        dimension = WorkItemProperty.objects.get(project=seeded, is_grouping_dimension=True)
        attributed = WorkItemPropertyValue.objects.filter(
            property=dimension, issue_id__in=reports.values_list("issue_id", flat=True)
        )

        assert reports.count() == attributed.count() > 0

    def test_one_report_reaches_two_accounts(self, seeded):
        """A multi-select dimension is only worth having if the seed exercises it."""
        dimension = WorkItemProperty.objects.get(project=seeded, is_grouping_dimension=True)
        widths = [
            len(value.value)
            for value in WorkItemPropertyValue.objects.filter(property=dimension)
            if isinstance(value.value, list)
        ]

        assert max(widths) > 1

    def test_the_noticeboard_carries_posts_that_are_not_all_engineering(self, seeded):
        posts = EntityUpdate.objects.filter(project=seeded, parent__isnull=True)
        topics = EntityUpdateLabel.objects.filter(entity_update__in=posts)

        assert posts.count() >= 3
        assert topics.values("label_id").distinct().count() >= 2

    def test_field_reports_carry_a_work_item_type(self, seeded):
        """The seed looks the type up by name, so a rename would silently untype them.

        `IssueType.objects.filter(name="Bug").first()` returns None rather than raising, and
        an untyped intake row still saves -- the seed would go on "working" while the reports
        lost the one thing that marks them as defects.
        """
        reports = IntakeIssue.objects.filter(project=seeded).select_related("issue__type")

        assert reports.exists()
        assert {report.issue.type.name for report in reports if report.issue.type_id} == {"Bug"}
        assert not reports.filter(issue__type__isnull=True).exists()

    def test_intake_is_reachable_from_the_sidebar(self, seeded):
        """The panel links to Intake; a project with the module off would 404 the reader."""
        assert seeded.intake_view is True


@pytest.mark.unit
@pytest.mark.django_db
class TestSeededPages:
    """Pages was the one surface the seed left empty.

    Two things were invisible because of it: the Overview's meeting-notes panel links here,
    so the war room pointed at a blank list; and a folder in this product is a page with
    children, so a flat seed cannot demonstrate the hierarchy at all.
    """

    def test_the_project_has_a_page_tree_not_a_flat_list(self, seeded):
        pages = Page.objects.filter(project_pages__project=seeded).distinct()
        parents = pages.filter(parent__isnull=True)
        children = pages.filter(parent__isnull=False)

        assert parents.count() >= 3
        assert children.count() >= 4
        # Every child hangs off a folder that belongs to the same project.
        assert set(children.values_list("parent_id", flat=True)) <= set(parents.values_list("id", flat=True))

    def test_documents_carry_body_text_and_a_search_stripe(self, seeded):
        """A document seeded with no body is a title in a list, which demonstrates nothing.

        Folders are excluded on purpose -- they render no body, so seeding one would put
        prose where the product never shows it.
        """
        documents = Page.objects.filter(project_pages__project=seeded, is_folder=False).distinct()

        assert documents.exists()
        assert all(p.description_html.strip() not in ("", "<p></p>") for p in documents)
        assert all((p.description_stripped or "").strip() for p in documents)

    def test_the_containers_are_declared_folders(self, seeded):
        """Every page holding children must be a folder; only folders may hold them."""
        pages = Page.objects.filter(project_pages__project=seeded).distinct()
        holders = {p.parent_id for p in pages if p.parent_id}

        assert holders
        assert all(Page.objects.get(pk=pid).is_folder for pid in holders)
        assert not pages.filter(is_folder=True, parent__isnull=False).exclude(
            parent__is_folder=True
        ).exists()

    def test_reseeding_does_not_strand_the_previous_pages(self, seeded, workspace):
        """Pages reach a project through a join row, so the cascade leaves them behind.

        Saved views had exactly this bug and `purge` had to learn about them explicitly;
        pages are the same shape and needed the same treatment.
        """
        before = Page.objects.filter(project_pages__project=seeded).distinct().count()
        assert before > 0

        call_command("seed_testing_demo", workspace=workspace.slug, identifier="DEMO", force=True, stdout=StringIO())

        reseeded = Project.objects.get(workspace=workspace, identifier="DEMO")
        # Same count, not double: the old tree was removed rather than accumulated beside it.
        assert Page.objects.filter(project_pages__project=reseeded).distinct().count() == before


@pytest.mark.unit
@pytest.mark.django_db
class TestSeedReport:
    """The summary must be counted from what was built, never restated from the design.

    `_breakdown` already carries that rule in its docstring, having once printed eleven
    stories against ten that existed. The lines beside it did not follow it: the report
    announced `types Epic / Feature / Story` while the seed created five types, Bug and
    Task included, and kept announcing it after `Task` became the fourth level of the
    hierarchy. A reader checking whether this project models implementation work was told
    no by the one output they were given.

    These assertions compare the printed line against the rows the same run created, so a
    literal reintroduced later fails here rather than quietly misdescribing the project.
    """

    @pytest.fixture
    def report(self, workspace):
        out = StringIO()
        call_command("seed_testing_demo", workspace=workspace.slug, identifier="DEMO", stdout=out)
        return out.getvalue()

    @staticmethod
    def _line(report, label):
        for raw in report.splitlines():
            if raw.startswith(f"    {label} "):
                return raw
        raise AssertionError(f"the report has no {label!r} line:\n{report}")

    @staticmethod
    def _numbers(line):
        return [int(token) for token in re.findall(r"\d+", line)]

    def test_the_types_line_names_every_type_the_seed_enabled(self, report, workspace):
        project = Project.objects.get(workspace=workspace, identifier="DEMO")
        enabled = set(
            IssueType.objects.filter(project_issue_types__project=project).values_list("name", flat=True)
        )
        assert enabled == {"Epic", "Feature", "Story", "Bug", "Task"}

        line = self._line(report, "types")
        assert {name for name in enabled if name in line} == enabled, line

    def test_the_epic_count_is_the_epics_that_exist(self, report, workspace):
        project = Project.objects.get(workspace=workspace, identifier="DEMO")
        epics = Issue.issue_objects.filter(project=project, type__is_epic=True).count()

        assert self._numbers(self._line(report, "epics"))[0] == epics

    def test_the_epic_state_groups_read_as_a_lifecycle(self, report):
        """Alphabetical order puts `cancelled` second, which reads as a stage of progress."""
        line = self._line(report, "epics")
        positions = [line.find(group) for group in ("backlog", "unstarted", "started", "cancelled")]
        assert all(position >= 0 for position in positions), line
        assert positions == sorted(positions), line

    def test_the_contract_counts_match_the_library(self, report, workspace):
        project = Project.objects.get(workspace=workspace, identifier="DEMO")
        cases, folders = self._numbers(self._line(report, "contracts"))[:2]

        assert cases == Case.objects.filter(project=project).count()
        assert folders == Folder.objects.filter(project=project).count()

    def test_the_evidence_counts_match_the_rows(self, report, workspace):
        project = Project.objects.get(workspace=workspace, identifier="DEMO")

        assert self._numbers(self._line(report, "runs"))[0] == Run.objects.filter(project=project).count()
        assert (
            self._numbers(self._line(report, "automation"))[0]
            == AutomationLink.objects.filter(project=project).count()
        )
        assert (
            self._numbers(self._line(report, "release"))[0]
            == ReleaseEvidence.objects.filter(project=project).count()
        )

    def test_the_relation_counts_match_the_edges(self, report, workspace):
        project = Project.objects.get(workspace=workspace, identifier="DEMO")
        relations = IssueRelation.objects.filter(project=project)
        line = self._line(report, "relations")

        for relation_type in ("blocked_by", "relates_to"):
            count = relations.filter(relation_type=relation_type).count()
            assert f"{count} {relation_type}" in line, line
