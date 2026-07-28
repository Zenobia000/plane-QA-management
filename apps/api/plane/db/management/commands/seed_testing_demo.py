# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import datetime
from typing import Any

# Django imports
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

# Module imports
from plane.db.models import (
    Cycle,
    CycleIssue,
    Issue,
    IssueType,
    Module,
    ModuleIssue,
    Project,
    ProjectIssueType,
    ProjectMember,
    State,
    User,
    Workspace,
)
from plane.db.models.state import DEFAULT_STATES
from plane.testing.services import (
    create_defect_from_result,
    create_fixed_test_run,
    create_test_case,
    create_test_folder,
    link_test_case_to_work_item,
    record_test_result,
)

BUILD = "2026.08.b7d40e1"


def _step(action, expected):
    return {"action": {"text": action}, "expected_result": {"text": expected}}


class Command(BaseCommand):
    help = (
        "Seed a traceability demo project: Epic to Feature to Story, each story "
        "contracted by test cases, with a run, a defect and a retest closing the "
        "evidence loop. Also reproduces the known reporting gaps so they can be "
        "observed rather than argued about. See docs/planning/testing-product-definition.md."
    )

    def add_arguments(self, parser):
        parser.add_argument("--workspace", required=True, help="Workspace slug to seed into")
        parser.add_argument("--identifier", default="DEMO", help="Project identifier (default: DEMO)")
        parser.add_argument(
            "--owner",
            default=None,
            help="Email of the seeding user; defaults to the workspace owner",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete an existing project with the same identifier before seeding",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> str | None:
        try:
            workspace = Workspace.objects.get(slug=options["workspace"])
        except Workspace.DoesNotExist:
            raise CommandError(f"Workspace '{options['workspace']}' does not exist.")

        if options["owner"]:
            try:
                owner = User.objects.get(email=options["owner"])
            except User.DoesNotExist:
                raise CommandError(f"User '{options['owner']}' does not exist.")
        else:
            owner = workspace.owner
            if owner is None:
                raise CommandError("The workspace has no owner; pass --owner explicitly.")

        identifier = options["identifier"].upper()
        existing = Project.objects.filter(workspace=workspace, identifier=identifier)
        if existing.exists():
            if not options["force"]:
                raise CommandError(
                    f"Project '{identifier}' already exists in '{workspace.slug}'. "
                    "Re-run with --force to replace it; every work item, test case, run and "
                    "result it holds will be deleted."
                )
            existing.delete()
            self.stdout.write(self.style.WARNING(f"Replaced the existing '{identifier}' project."))

        project = self._create_project(workspace, owner, identifier)
        states = {state.group: state for state in State.objects.filter(project=project)}
        types = self._create_work_item_types(workspace, project)
        module, cycle = self._create_planning(workspace, project, owner)
        items = self._create_hierarchy(workspace, project, owner, types, states, module, cycle)
        cases = self._create_contracts(project, items)
        run, run_cases = self._execute(project, owner, cases, module, cycle)
        defect = self._close_the_loop(project, owner, run_cases, states)

        self._report(project, workspace, items, cases, run, defect)
        return None

    def _create_project(self, workspace, owner, identifier):
        project = Project.objects.create(
            workspace=workspace,
            name="Traceability Demo",
            identifier=identifier,
            description=(
                "Epic to Feature to Story, each story contracted by test cases, "
                "evidence looping back through defect and retest."
            ),
            project_lead=owner,
            created_by=owner,
        )
        State.objects.bulk_create(
            [
                State(
                    name=state["name"],
                    color=state["color"],
                    project=project,
                    sequence=state["sequence"],
                    workspace=workspace,
                    group=state["group"],
                    default=state.get("default", False),
                    created_by=owner,
                )
                for state in DEFAULT_STATES
            ]
        )
        role = ProjectMember.objects.filter(workspace=workspace).values_list("role", flat=True).first() or 20
        ProjectMember.objects.create(
            project=project, member=owner, role=role, workspace=workspace, created_by=owner
        )
        return project

    def _create_work_item_types(self, workspace, project):
        """Work item types carry the work-breakdown level.

        The requirement-nature classification is a separate axis and gets its own
        type here, so the two never collapse into a single field -- a functional
        requirement can perfectly well carry a performance threshold.
        """
        definitions = [
            ("Epic", "A business capability spanning several features.", 0, True),
            ("Feature", "A coherent set of system capabilities.", 1, False),
            ("Story", "User-visible value delivered in one iteration.", 2, False),
            ("Quality requirement", "A non-functional constraint on how well the system performs.", 2, False),
        ]
        types = {}
        for name, description, level, is_epic in definitions:
            issue_type, _ = IssueType.objects.get_or_create(
                workspace=workspace,
                name=name,
                defaults={"description": description, "is_epic": is_epic, "level": level},
            )
            ProjectIssueType.objects.get_or_create(
                project=project,
                issue_type=issue_type,
                defaults={"level": int(level), "is_default": name == "Story"},
            )
            types[name] = issue_type
        return types

    def _create_planning(self, workspace, project, owner):
        module = Module.objects.create(
            workspace=workspace, project=project, name="生產履歷", created_by=owner, lead=owner
        )
        today = timezone.now().date()
        as_datetime = lambda day: timezone.make_aware(datetime.datetime.combine(day, datetime.time.min))  # noqa: E731
        cycle = Cycle.objects.create(
            workspace=workspace,
            project=project,
            name="Sprint 2026-08A",
            start_date=as_datetime(today - datetime.timedelta(days=4)),
            end_date=as_datetime(today + datetime.timedelta(days=10)),
            owned_by=owner,
            created_by=owner,
        )
        return module, cycle

    def _create_hierarchy(self, workspace, project, owner, types, states, module, cycle):
        def item(name, description, issue_type, state, parent=None, priority="high", in_cycle=True):
            issue = Issue.objects.create(
                workspace=workspace,
                project=project,
                name=name,
                description_html=f"<p>{description}</p>",
                state=states[state],
                priority=priority,
                type=types[issue_type],
                parent=parent,
                created_by=owner,
                start_date=cycle.start_date.date(),
                target_date=cycle.end_date.date(),
            )
            if in_cycle:
                CycleIssue.objects.create(
                    workspace=workspace, project=project, cycle=cycle, issue=issue, created_by=owner
                )
            ModuleIssue.objects.create(
                workspace=workspace, project=project, module=module, issue=issue, created_by=owner
            )
            return issue

        epic = item(
            "生產履歷與異常追溯能力",
            "讓 IE 能追查任一產品在各工站的處理與異常紀錄。",
            "Epic",
            "started",
            in_cycle=False,
        )
        feature_query = item(
            "工單與序號生產履歷查詢", "支援以工單編號或產品序號查詢完整站點履歷。", "Feature", "started", parent=epic
        )
        feature_ng = item(
            "NG 事件修正與審核", "IE 可修正 AI 誤判,主管可審核修正紀錄。", "Feature", "started", parent=epic
        )
        return {
            "epic": epic,
            "feature_query": feature_query,
            "feature_ng": feature_ng,
            "story_wo": item(
                "IE 以工單編號查詢生產履歷",
                "輸入工單編號後顯示各工站的進出站時間與推論結果。",
                "Story",
                "started",
                parent=feature_query,
            ),
            "story_sn": item(
                "IE 以產品序號查詢生產履歷",
                "輸入產品序號後顯示該件產品的完整履歷。",
                "Story",
                "unstarted",
                parent=feature_query,
            ),
            "story_fix": item(
                "IE 修正 AI 誤判結果",
                "IE 可將誤判的 NG 標記為誤報並填寫原因。",
                "Story",
                "started",
                parent=feature_ng,
            ),
            # Scheduled into the sprint with no acceptance contract at all. That is
            # the Definition-of-Ready violation the release gate has to catch:
            # a backlog item nobody has committed to yet would not be one.
            "story_review": item(
                "主管審核修正紀錄",
                "已排入 sprint 卻未建立任何驗收契約,示範 Definition of Ready 違規。",
                "Story",
                "unstarted",
                parent=feature_ng,
                priority="medium",
            ),
            "nfr_perf": item(
                "履歷查詢 P95 回應時間低於 2 秒",
                "在 1,000 萬筆履歷資料下,查詢 API 的 P95 不得超過 2,000 ms。",
                "Quality requirement",
                "started",
                parent=feature_query,
            ),
            "nfr_sec": item(
                "使用者僅能查詢被授權廠區的資料",
                "跨廠區查詢必須被拒絕並留下稽核紀錄。",
                "Quality requirement",
                "started",
                parent=epic,
            ),
        }

    def _create_contracts(self, project, items):
        root = create_test_folder(project_id=project.id, name="生產履歷", sort_order=1000)
        folders = {
            "query": create_test_folder(project_id=project.id, name="履歷查詢", parent_id=root.id, sort_order=1000),
            "ng": create_test_folder(project_id=project.id, name="NG 修正", parent_id=root.id, sort_order=2000),
            "quality": create_test_folder(project_id=project.id, name="品質門檻", parent_id=root.id, sort_order=3000),
        }

        def case(title, folder, tags, steps, priority="high", preconditions=None):
            return create_test_case(
                project_id=project.id,
                title=title,
                folder_id=folders[folder].id,
                priority=priority,
                tags=tags,
                preconditions=preconditions or {},
                steps=steps,
            )

        cases = {
            "wo_happy": case(
                "以有效工單編號查詢可顯示完整站點履歷",
                "query",
                ["functional", "manual", "smoke"],
                [
                    _step("輸入工單編號 WO-20260728-001 並查詢", "顯示該工單經歷的所有工站"),
                    _step("檢視站點列表", "每站顯示進站與離站時間"),
                    _step("展開任一工站", "顯示 AI 推論結果與人工修正紀錄"),
                ],
                preconditions={"text": "工單 WO-20260728-001 已存在且使用者具 CN21 廠區權限"},
            ),
            "wo_notfound": case(
                "查詢不存在的工單應顯示明確訊息",
                "query",
                ["functional", "manual", "negative"],
                [_step("輸入不存在的工單編號並查詢", "顯示查無資料訊息,不出現錯誤畫面")],
                priority="medium",
            ),
            "sn_happy": case(
                "以產品序號查詢可顯示該件產品履歷",
                "query",
                ["functional", "manual"],
                [_step("輸入產品序號 SN-A1B2C3 並查詢", "顯示該序號的完整站點履歷")],
                preconditions={"text": "序號 SN-A1B2C3 已完成三個工站"},
            ),
            "fix_happy": case(
                "IE 可將誤判 NG 標記為誤報",
                "ng",
                ["functional", "manual"],
                [
                    _step("開啟該 NG 事件並選擇標記為誤報", "顯示原因輸入欄位"),
                    _step("填寫原因並送出", "事件狀態變更為已修正並記錄修正者"),
                ],
                preconditions={"text": "存在一筆 AI 判定為 NG 的事件"},
            ),
            "fix_audit": case(
                "修正操作必須留下稽核紀錄",
                "ng",
                ["functional", "manual", "negative"],
                [_step("完成一次誤報修正後檢視稽核紀錄", "紀錄包含操作者、時間、修正前後值")],
                priority="medium",
            ),
            "api_auto": case(
                "履歷查詢 API 在有效請求下回應 200",
                "query",
                ["functional", "automated"],
                [_step("GET /api/trace?wo=WO-20260728-001", "回應 200 且 payload 含 stations 陣列")],
                priority="medium",
            ),
            # The expectation is structured so it could be charted and judged
            # automatically. The JSONField accepts it today; the UI cannot render
            # it yet, which is the point -- gap #17 made observable.
            "perf": create_test_case(
                project_id=project.id,
                title="履歷查詢 P95 回應時間低於 2,000 ms",
                folder_id=folders["quality"].id,
                priority="high",
                tags=["performance", "automated", "threshold"],
                preconditions={
                    "text": "資料庫含 1,000 萬筆履歷 · 200 VU · 持續 5 分鐘",
                    "dataset_rows": 10_000_000,
                    "vus": 200,
                },
                steps=[
                    {
                        "action": {"text": "以隨機有效工單編號持續發送查詢請求", "tool": "k6"},
                        "expected_result": {
                            "text": "P95 回應時間 < 2,000 ms",
                            "metric": "http_req_duration_p95",
                            "operator": "<",
                            "threshold": 2000,
                            "unit": "ms",
                        },
                    }
                ],
            ),
            "sec": case(
                "跨廠區查詢應被拒絕並留下稽核紀錄",
                "quality",
                ["security", "manual", "negative"],
                [
                    _step("以 CN21 使用者查詢 CN22 的工單", "系統拒絕提供資料"),
                    _step("檢視稽核紀錄", "留下一筆未授權存取事件"),
                ],
                priority="urgent",
            ),
        }

        # Contracts attach at Story and Quality-requirement level. Feature and Epic
        # stay unlinked on purpose: that is what makes the missing hierarchy
        # roll-up visible in the coverage report.
        for key, item_key in (
            ("wo_happy", "story_wo"),
            ("wo_notfound", "story_wo"),
            ("api_auto", "story_wo"),
            ("sn_happy", "story_sn"),
            ("fix_happy", "story_fix"),
            ("fix_audit", "story_fix"),
            ("perf", "nfr_perf"),
            ("sec", "nfr_sec"),
        ):
            link_test_case_to_work_item(
                test_case_id=cases[key].id, issue_id=items[item_key].id, project_id=project.id
            )
        return cases

    def _execute(self, project, owner, cases, module, cycle):
        run = create_fixed_test_run(
            project_id=project.id,
            name="Sprint 2026-08A 回歸驗證",
            test_case_ids=[case.id for case in cases.values()],
            build=BUILD,
            cycle_id=cycle.id,
            module_id=module.id,
            description={"text": "涵蓋本 sprint 的功能契約與品質門檻。"},
        )
        by_case = {run_case.test_case_id: run_case for run_case in run.run_cases.all()}
        run_cases = {key: by_case[case.id] for key, case in cases.items()}

        for key, actual, duration in (
            ("wo_happy", "三個工站皆正確顯示,含推論結果與修正紀錄。", 38000),
            ("wo_notfound", "顯示查無資料,無錯誤畫面。", 9000),
            ("sn_happy", "序號履歷完整。", 27000),
            ("fix_audit", "稽核紀錄含操作者、時間與前後值。", 15000),
            ("api_auto", "CI:200,stations 長度 3。", 240),
            ("sec", "跨廠區查詢被拒,稽核紀錄已產生。", 31000),
        ):
            record_test_result(
                run_case_id=run_cases[key].id,
                project_id=project.id,
                status="passed",
                executed_by=owner,
                actual_result={"text": actual},
                duration_ms=duration,
            )

        record_test_result(
            run_case_id=run_cases["perf"].id,
            project_id=project.id,
            status="passed",
            executed_by=owner,
            actual_result={
                "text": "P95 1,840 ms(門檻 2,000 ms,餘裕 8%)",
                "measured": 1840,
                "unit": "ms",
                "metric": "http_req_duration_p95",
                "source": "k6 · CI run #482",
            },
            duration_ms=300000,
        )
        return run, run_cases

    def _close_the_loop(self, project, owner, run_cases, states):
        failure = record_test_result(
            run_case_id=run_cases["fix_happy"].id,
            project_id=project.id,
            status="failed",
            executed_by=owner,
            actual_result={"text": "送出修正後狀態未更新,重整才看得到變更;稽核紀錄缺少修正前值。"},
            duration_ms=52000,
        )
        defect = create_defect_from_result(
            result_id=failure.id,
            run_case_id=run_cases["fix_happy"].id,
            project_id=project.id,
            created_by=owner,
            priority="urgent",
        ).issue
        # The defect stays untyped, exactly as the service leaves it. Typing it
        # would hide that the coverage report counts defects as requirements.
        Issue.objects.filter(id=defect.id).update(state=states["completed"])
        record_test_result(
            run_case_id=run_cases["fix_happy"].id,
            project_id=project.id,
            status="passed",
            executed_by=owner,
            actual_result={"text": "修正後重驗:狀態即時更新,稽核紀錄含修正前後值。"},
            duration_ms=48000,
        )
        return defect

    def _report(self, project, workspace, items, cases, run, defect):
        base = f"/{workspace.slug}/projects/{project.id}/testing"
        write = self.stdout.write
        write(self.style.SUCCESS(f"Seeded {project.identifier} ({project.id})"))
        write("  1 epic / 2 features / 4 stories / 2 quality requirements")
        write(f"  {len(cases)} test cases · 1 run pinned at build {BUILD}")
        write(f"  1 failure -> defect {project.identifier}-{defect.sequence_id} -> retest appended")
        write("")
        write("Gaps this sample makes observable (see docs/planning/testing-product-definition.md):")
        write("  #14  the epic and both features read as uncovered although 8 contracts sit beneath them,")
        write("       the untyped defect is listed as a requirement, and coverage_percent reports the")
        write("       share of cases that are linked rather than the share of requirements covered")
        write("  #18  a scheduled story with no acceptance contract now blocks the release gate")
        write("  #17  the threshold case carries a structured expectation the UI renders as plain text")
        write("")
        write(f"  overview  {base}/overview")
        write(f"  cases     {base}/cases")
        write(f"  run       {base}/runs/{run.id}")
