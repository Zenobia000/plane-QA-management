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
    ReleaseEvidence,
    State,
    User,
    WorkItemProperty,
    WorkItemPropertyOption,
    WorkItemPropertyValue,
    Workspace,
)
from plane.db.models.state import DEFAULT_STATES
from plane.testing.services import (
    create_defect_from_result,
    create_fixed_test_run,
    create_test_case,
    create_test_folder,
    link_test_case_to_work_item,
    publish_test_case_version,
    record_test_result,
)

PREVIOUS_BUILD = "2026.07.c1a8e42"
CURRENT_BUILD = "2026.08.b7d40e1"


def _step(action, expected):
    return {"action": {"text": action}, "expected_result": {"text": expected}}


class Command(BaseCommand):
    help = (
        "Seed a traceability demo modelled on a shop-floor quality platform. Builds both "
        "axes the product definition separates -- the work breakdown (epic, feature, story) "
        "and the requirement nature (functional, non-functional) -- then contracts, executes, "
        "and closes the evidence loop across two sprints. See "
        "docs/planning/testing-product-definition.md."
    )

    def add_arguments(self, parser):
        parser.add_argument("--workspace", required=True, help="Workspace slug to seed into")
        parser.add_argument("--identifier", default="DEMO", help="Project identifier (default: DEMO)")
        parser.add_argument("--owner", default=None, help="Email of the seeding user; defaults to the workspace owner")
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
        kind_property = self._create_requirement_kind_property(project)
        modules, cycles = self._create_planning(workspace, project, owner)
        items = self._create_hierarchy(workspace, project, owner, types, states, modules, cycles, kind_property)
        cases = self._create_contracts(project, items)
        runs = self._execute(project, owner, cases, modules, cycles)
        defect = self._close_the_loop(project, owner, runs, states)
        self._record_system_level_nfrs(workspace, project, owner)

        self._report(project, workspace, items, cases, runs, defect)
        return None

    def _create_project(self, workspace, owner, identifier):
        project = Project.objects.create(
            workspace=workspace,
            name="Shop-floor Quality Platform",
            identifier=identifier,
            description=(
                "Production traceability and AI defect review. Two axes: the work breakdown "
                "runs epic to feature to story, and every requirement is classified functional "
                "or non-functional independently of where it sits."
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
        ProjectMember.objects.create(project=project, member=owner, role=role, workspace=workspace, created_by=owner)
        return project

    def _create_work_item_types(self, workspace, project):
        """Axis one: how the work is broken down.

        Epic, feature and story only. An earlier version of this seed also created a
        "Quality requirement" type sitting beside Story, which quietly folded the
        requirement-nature axis into the breakdown axis -- exactly the collapse
        section 5 warns against. Nature is a property; see below.
        """
        definitions = [
            ("Epic", "A business capability spanning several features.", 0, True),
            ("Feature", "A coherent set of system capabilities.", 1, False),
            ("Story", "User-visible value delivered in one iteration.", 2, False),
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

    def _create_requirement_kind_property(self, project):
        """Axis two: what kind of requirement it is.

        Crosses the breakdown rather than nesting inside it -- an epic, a feature and
        a story can each be functional or non-functional. Keeping it a property is
        what lets a feature carry a quality constraint without inventing a parallel
        hierarchy for it.
        """
        prop = WorkItemProperty.objects.create(
            project=project,
            workspace=project.workspace,
            name="Requirement kind",
            description="Functional requirements say what the system does; non-functional ones say how well.",
            kind=WorkItemProperty.Kind.SELECT,
            sort_order=1000,
        )
        for index, (label, value) in enumerate(
            [("Functional (FR)", "functional"), ("Non-functional (NFR)", "non_functional")]
        ):
            WorkItemPropertyOption.objects.create(
                property=prop,
                project=project,
                workspace=project.workspace,
                label=label,
                value=value,
                sort_order=(index + 1) * 1000,
            )
        return prop

    def _create_planning(self, workspace, project, owner):
        def as_datetime(day):
            return timezone.make_aware(datetime.datetime.combine(day, datetime.time.min))

        modules = {
            name: Module.objects.create(
                workspace=workspace, project=project, name=name, created_by=owner, lead=owner
            )
            for name in ("生產履歷", "AI 推論服務")
        }
        today = timezone.now().date()
        cycles = {
            "previous": Cycle.objects.create(
                workspace=workspace,
                project=project,
                name="Sprint 2026-07B",
                start_date=as_datetime(today - datetime.timedelta(days=18)),
                end_date=as_datetime(today - datetime.timedelta(days=5)),
                owned_by=owner,
                created_by=owner,
            ),
            "current": Cycle.objects.create(
                workspace=workspace,
                project=project,
                name="Sprint 2026-08A",
                start_date=as_datetime(today - datetime.timedelta(days=4)),
                end_date=as_datetime(today + datetime.timedelta(days=10)),
                owned_by=owner,
                created_by=owner,
            ),
        }
        return modules, cycles

    def _create_hierarchy(self, workspace, project, owner, types, states, modules, cycles, kind_property):
        """Three axes at once.

        Breakdown gives an item its parent, requirement kind gives it a property, and
        the cycle gives it a time box. None of the three is derivable from the others:
        a non-functional requirement can sit under any feature, in any sprint.
        """
        options = {option.value: option for option in kind_property.options.all()}

        def item(name, description, level, state, kind, parent=None, cycle=None, module=None, priority="high"):
            issue = Issue.objects.create(
                workspace=workspace,
                project=project,
                name=name,
                description_html=f"<p>{description}</p>",
                state=states[state],
                priority=priority,
                type=types[level],
                parent=parent,
                created_by=owner,
                start_date=cycles["previous"].start_date.date() if cycle == "previous" else None,
                target_date=cycles[cycle].end_date.date() if cycle else None,
            )
            WorkItemPropertyValue.objects.create(
                project=project,
                workspace=workspace,
                property=kind_property,
                issue=issue,
                value={"value": kind, "label": options[kind].label},
                created_by=owner,
            )
            if cycle:
                CycleIssue.objects.create(
                    workspace=workspace, project=project, cycle=cycles[cycle], issue=issue, created_by=owner
                )
            if module:
                ModuleIssue.objects.create(
                    workspace=workspace, project=project, module=modules[module], issue=issue, created_by=owner
                )
            return issue

        trace = item(
            "生產履歷與異常追溯能力",
            "讓 IE 能追查任一產品在各工站的處理結果與異常紀錄。",
            "Epic", "started", "functional", module="生產履歷",
        )
        inference = item(
            "AI 推論服務可靠性",
            "推論結果必須及時、穩定地回寫到工單,否則產線判讀失去依據。",
            "Epic", "started", "non_functional", module="AI 推論服務",
        )
        query = item(
            "工單與序號履歷查詢", "支援以工單編號或產品序號查詢完整站點履歷。",
            "Feature", "started", "functional", parent=trace, module="生產履歷",
        )
        review = item(
            "NG 事件修正與審核", "IE 可修正 AI 誤判,主管審核後回寫 MES。",
            "Feature", "started", "functional", parent=trace, module="生產履歷",
        )
        latency = item(
            "推論結果即時性", "推論完成到工單可見的延遲必須可控。",
            "Feature", "started", "non_functional", parent=inference, module="AI 推論服務",
        )

        return {
            "epic_trace": trace,
            "epic_inference": inference,
            "feature_query": query,
            "feature_review": review,
            "feature_latency": latency,
            # --- Sprint 2026-07B, delivered ---
            "wo_query": item(
                "IE 以工單編號查詢生產履歷", "輸入工單編號後顯示各工站的進出站時間與推論結果。",
                "Story", "completed", "functional", parent=query, cycle="previous", module="生產履歷",
            ),
            "sn_query": item(
                "IE 以產品序號查詢生產履歷", "輸入產品序號後顯示該件產品的完整履歷。",
                "Story", "completed", "functional", parent=query, cycle="previous", module="生產履歷",
            ),
            # A quality constraint on the query feature. It is a story-shaped unit of
            # work in its own sprint, and non-functional -- the two axes are independent.
            "query_latency": item(
                "履歷查詢 P95 回應時間低於 2 秒", "在 1,000 萬筆履歷資料下,查詢 API 的 P95 不得超過 2,000 ms。",
                "Story", "completed", "non_functional", parent=query, cycle="previous", module="生產履歷",
            ),
            # --- Carried into Sprint 2026-08A ---
            "export": item(
                "履歷匯出為稽核報表", "自 Sprint 2026-07B 順延:匯出格式未定案,重新排入本期。",
                "Story", "started", "functional", parent=query, cycle="current", module="生產履歷",
                priority="medium",
            ),
            # --- Sprint 2026-08A ---
            "mark_false": item(
                "IE 將誤判 NG 標記為誤報", "IE 可將誤判的 NG 標記為誤報並填寫原因。",
                "Story", "started", "functional", parent=review, cycle="current", module="生產履歷",
            ),
            "writeback": item(
                "修正結果回寫 MES", "審核通過的修正需在 30 秒內回寫 MES。",
                "Story", "started", "functional", parent=review, cycle="current", module="生產履歷",
            ),
            # Scheduled into the sprint with no acceptance contract at all -- the
            # Definition-of-Ready violation the release gate has to catch.
            "supervisor": item(
                "主管審核修正紀錄", "已排入本期卻未建立任何驗收契約,示範 Definition of Ready 違規。",
                "Story", "unstarted", "functional", parent=review, cycle="current", module="生產履歷",
                priority="medium",
            ),
            "authorization": item(
                "使用者僅能存取授權廠區資料", "跨廠區查詢必須被拒絕並留下稽核紀錄。",
                "Story", "started", "non_functional", parent=review, cycle="current", module="生產履歷",
                priority="urgent",
            ),
            "inference_latency": item(
                "推論結果 5 秒內回寫工單", "推論完成後 5 秒內,工單頁面必須看得到結果。",
                "Story", "started", "functional", parent=latency, cycle="current", module="AI 推論服務",
            ),
            "inference_failure": item(
                "推論服務失敗率低於 0.5%", "連續 24 小時的推論請求失敗率不得超過 0.5%。",
                "Story", "unstarted", "non_functional", parent=latency, cycle="current", module="AI 推論服務",
                priority="medium",
            ),
        }

    def _create_contracts(self, project, items):
        root = create_test_folder(project_id=project.id, name="生產履歷", sort_order=1000)
        folders = {
            "query": create_test_folder(project_id=project.id, name="履歷查詢", parent_id=root.id, sort_order=1000),
            "review": create_test_folder(project_id=project.id, name="NG 修正", parent_id=root.id, sort_order=2000),
            "quality": create_test_folder(project_id=project.id, name="品質門檻", parent_id=root.id, sort_order=3000),
            "inference": create_test_folder(project_id=project.id, name="AI 推論", parent_id=root.id, sort_order=4000),
        }

        def case(key, title, folder, tags, steps, priority="high", preconditions=None, case_type="functional"):
            return create_test_case(
                project_id=project.id, title=title, folder_id=folders[folder].id, priority=priority,
                case_type=case_type, tags=tags, preconditions=preconditions or {}, steps=steps,
            )

        cases = {
            "wo_happy": case(
                "wo_happy", "以有效工單編號查詢可顯示完整站點履歷", "query", ["functional", "manual", "smoke"],
                [
                    _step("輸入工單編號 WO-20260728-001 並查詢", "顯示該工單經歷的所有工站"),
                    _step("檢視站點列表", "每站顯示進站與離站時間"),
                    _step("展開任一工站", "顯示 AI 推論結果與人工修正紀錄"),
                ],
                preconditions={"text": "工單 WO-20260728-001 已存在,使用者具 CN21 廠區權限"},
            ),
            "wo_notfound": case(
                "wo_notfound", "查詢不存在的工單應顯示明確訊息", "query", ["functional", "manual", "negative"],
                [_step("輸入不存在的工單編號並查詢", "顯示查無資料訊息,不出現錯誤畫面")], priority="medium",
            ),
            "sn_happy": case(
                "sn_happy", "以產品序號查詢可顯示該件產品履歷", "query", ["functional", "manual"],
                [_step("輸入產品序號 SN-A1B2C3 並查詢", "顯示該序號的完整站點履歷")],
                preconditions={"text": "序號 SN-A1B2C3 已完成三個工站"},
            ),
            "export_csv": case(
                "export_csv", "履歷可匯出為稽核用 CSV", "query", ["functional", "manual"],
                [
                    _step("在履歷頁選擇匯出", "產生 CSV 下載"),
                    _step("開啟 CSV", "欄位含工單、序號、工站、進出站時間、推論結果、修正者"),
                ],
                priority="medium",
            ),
            "mark_false_happy": case(
                "mark_false_happy", "IE 可將誤判 NG 標記為誤報", "review", ["functional", "manual"],
                [
                    _step("開啟該 NG 事件並選擇標記為誤報", "顯示原因輸入欄位"),
                    _step("填寫原因並送出", "事件狀態變更為已修正並記錄修正者"),
                ],
                preconditions={"text": "存在一筆 AI 判定為 NG 的事件"},
            ),
            "mark_false_audit": case(
                "mark_false_audit", "修正操作必須留下稽核紀錄", "review", ["functional", "manual", "negative"],
                [_step("完成一次誤報修正後檢視稽核紀錄", "紀錄含操作者、時間、修正前後值")], priority="medium",
            ),
            "writeback_mes": case(
                "writeback_mes", "審核通過的修正 30 秒內回寫 MES", "review", ["functional", "manual"],
                [
                    _step("主管審核通過一筆修正", "顯示已送出回寫"),
                    _step("查詢 MES 對應工單", "30 秒內可見更新後的判定結果"),
                ],
            ),
            "inference_visible": case(
                "inference_visible", "推論完成後 5 秒內工單可見結果", "inference", ["functional", "automated"],
                [_step("送出一張待推論影像並輪詢工單", "5 秒內工單顯示推論結果")], priority="medium",
            ),
            "api_contract": case(
                "api_contract", "履歷查詢 API 在有效請求下回應 200", "query", ["functional", "automated"],
                [_step("GET /api/trace?wo=WO-20260728-001", "回應 200 且 payload 含 stations 陣列")],
                priority="medium",
            ),
        }

        # Threshold contracts. The expectation is structured so it can be judged and
        # charted; prose in the same field could be neither.
        cases["query_p95"] = create_test_case(
            project_id=project.id, title="履歷查詢 P95 回應時間低於 2,000 ms",
            folder_id=folders["quality"].id, priority="high", case_type="performance",
            tags=["performance", "automated", "threshold"],
            preconditions={"text": "資料庫含 1,000 萬筆履歷 · 200 VU · 持續 5 分鐘", "dataset_rows": 10_000_000, "vus": 200},
            steps=[{
                "action": {"text": "以隨機有效工單編號持續發送查詢請求", "tool": "k6"},
                "expected_result": {
                    "text": "P95 回應時間 < 2,000 ms", "metric": "http_req_duration_p95",
                    "operator": "<", "threshold": 2000, "unit": "ms",
                },
            }],
        )
        cases["inference_failure_rate"] = create_test_case(
            project_id=project.id, title="推論服務 24 小時失敗率低於 0.5%",
            folder_id=folders["quality"].id, priority="high", case_type="reliability",
            tags=["reliability", "automated", "threshold"],
            preconditions={"text": "取樣連續 24 小時的推論請求", "window_hours": 24},
            steps=[{
                "action": {"text": "統計推論請求的失敗比例", "tool": "prometheus"},
                "expected_result": {
                    "text": "失敗率 < 0.5%", "metric": "inference_error_rate",
                    "operator": "<", "threshold": 0.5, "unit": "%",
                },
            }],
        )
        cases["cross_site"] = create_test_case(
            project_id=project.id, title="跨廠區查詢應被拒絕並留下稽核紀錄",
            folder_id=folders["quality"].id, priority="urgent", case_type="security",
            tags=["security", "manual", "negative"],
            preconditions={"text": "使用者僅具 CN21 廠區權限;工單 WO-20260728-999 屬於 CN22"},
            steps=[
                _step("以 CN21 使用者查詢 CN22 的工單", "系統拒絕提供資料"),
                _step("檢視稽核紀錄", "留下一筆未授權存取事件"),
            ],
        )

        for case_key, item_key in (
            ("wo_happy", "wo_query"), ("wo_notfound", "wo_query"), ("api_contract", "wo_query"),
            ("sn_happy", "sn_query"),
            ("export_csv", "export"),
            ("query_p95", "query_latency"),
            ("mark_false_happy", "mark_false"), ("mark_false_audit", "mark_false"),
            ("writeback_mes", "writeback"),
            ("cross_site", "authorization"),
            ("inference_visible", "inference_latency"),
            ("inference_failure_rate", "inference_failure"),
        ):
            link_test_case_to_work_item(
                test_case_id=cases[case_key].id, issue_id=items[item_key].id, project_id=project.id
            )
        return cases

    def _execute(self, project, owner, cases, modules, cycles):
        """One run per sprint, each scoped to its cycle.

        A run that is not bound to a cycle cannot be reported against the sprint that
        commissioned it, which is how planning and execution drift apart. Two runs also
        give the threshold cases a second measurement, so a trend exists rather than a
        single reading.
        """
        previous_keys = ["wo_happy", "wo_notfound", "sn_happy", "api_contract", "query_p95"]
        previous = create_fixed_test_run(
            project_id=project.id,
            name="Sprint 2026-07B 回歸驗證",
            test_case_ids=[cases[key].id for key in previous_keys],
            build=PREVIOUS_BUILD,
            cycle_id=cycles["previous"].id,
            module_id=modules["生產履歷"].id,
            description={"text": "上一期交付的查詢功能與效能門檻。"},
        )
        by_case = {run_case.test_case_id: run_case for run_case in previous.run_cases.all()}
        previous_cases = {key: by_case[cases[key].id] for key in previous_keys}

        for key, actual, duration in (
            ("wo_happy", "三個工站皆正確顯示,含推論結果與修正紀錄。", 38000),
            ("wo_notfound", "顯示查無資料,無錯誤畫面。", 9000),
            ("sn_happy", "序號履歷完整。", 27000),
            ("api_contract", "CI:200,stations 長度 3。", 240),
        ):
            record_test_result(
                run_case_id=previous_cases[key].id, project_id=project.id, status="passed",
                executed_by=owner, actual_result={"text": actual}, duration_ms=duration,
            )
        record_test_result(
            run_case_id=previous_cases["query_p95"].id, project_id=project.id, status="passed",
            executed_by=owner,
            actual_result={
                "text": "P95 1,910 ms(門檻 2,000 ms)", "measured": 1910, "unit": "ms",
                "metric": "http_req_duration_p95", "source": "k6 · CI run #451",
            },
            duration_ms=300000,
        )

        # Editing a contract after a run has pinned it is the invariant worth showing:
        # the closed sprint keeps the version it executed.
        publish_test_case_version(
            test_case_id=cases["wo_happy"].id, project_id=project.id,
            title="以有效工單編號查詢可顯示完整站點履歷", priority="high",
            case_type="functional", tags=["functional", "manual", "smoke"],
            preconditions={"text": "工單 WO-20260728-001 已存在,使用者具 CN21 廠區權限;瀏覽器語系為繁體中文"},
            steps=[
                _step("輸入工單編號 WO-20260728-001 並查詢", "顯示該工單經歷的所有工站"),
                _step("檢視站點列表", "每站顯示進站與離站時間"),
                _step("展開任一工站", "顯示 AI 推論結果與人工修正紀錄"),
                _step("切換語系為英文", "站點名稱與狀態皆已翻譯"),
            ],
        )

        current_keys = [
            "wo_happy", "sn_happy", "export_csv", "mark_false_happy", "mark_false_audit",
            "writeback_mes", "cross_site", "inference_visible", "api_contract",
            "query_p95", "inference_failure_rate",
        ]
        current = create_fixed_test_run(
            project_id=project.id,
            name="Sprint 2026-08A 回歸驗證",
            test_case_ids=[cases[key].id for key in current_keys],
            build=CURRENT_BUILD,
            cycle_id=cycles["current"].id,
            module_id=modules["生產履歷"].id,
            description={"text": "本期的 NG 修正與回寫,加上前期功能的回歸。"},
        )
        by_case = {run_case.test_case_id: run_case for run_case in current.run_cases.all()}
        current_cases = {key: by_case[cases[key].id] for key in current_keys}

        for key, actual, duration in (
            ("wo_happy", "回歸通過,語系切換後站點名稱正確。", 41000),
            ("sn_happy", "序號履歷完整。", 26000),
            ("mark_false_audit", "稽核紀錄含操作者、時間與前後值。", 15000),
            ("cross_site", "跨廠區查詢被拒,稽核紀錄已產生。", 31000),
            ("api_contract", "CI:200,stations 長度 3。", 230),
            ("inference_visible", "CI:平均 3.2 秒可見。", 3200),
        ):
            record_test_result(
                run_case_id=current_cases[key].id, project_id=project.id, status="passed",
                executed_by=owner, actual_result={"text": actual}, duration_ms=duration,
            )
        record_test_result(
            run_case_id=current_cases["query_p95"].id, project_id=project.id, status="passed",
            executed_by=owner,
            actual_result={
                "text": "P95 1,840 ms(門檻 2,000 ms,較上期改善 70 ms)", "measured": 1840, "unit": "ms",
                "metric": "http_req_duration_p95", "source": "k6 · CI run #482",
            },
            duration_ms=300000,
        )
        # A threshold that misses is still a passing-shaped measurement until someone
        # compares it, which is why the status is recorded as failed explicitly.
        record_test_result(
            run_case_id=current_cases["inference_failure_rate"].id, project_id=project.id, status="failed",
            executed_by=owner,
            actual_result={
                "text": "失敗率 0.8%,超出 0.5% 門檻", "measured": 0.8, "unit": "%",
                "metric": "inference_error_rate", "source": "prometheus · 24h window",
            },
            duration_ms=86400000,
        )
        record_test_result(
            run_case_id=current_cases["export_csv"].id, project_id=project.id, status="blocked",
            executed_by=owner,
            actual_result={"text": "匯出欄位規格尚未定案,無法驗證;此故事自上期順延。"},
            duration_ms=6000,
        )
        return {
            "previous": (previous, previous_cases),
            "current": (current, current_cases),
        }

    def _close_the_loop(self, project, owner, runs, states):
        current, current_cases = runs["current"]
        failure = record_test_result(
            run_case_id=current_cases["mark_false_happy"].id, project_id=project.id, status="failed",
            executed_by=owner,
            actual_result={"text": "送出修正後狀態未更新,重整才看得到變更;稽核紀錄缺少修正前值。"},
            duration_ms=52000,
        )
        defect = create_defect_from_result(
            result_id=failure.id, run_case_id=current_cases["mark_false_happy"].id,
            project_id=project.id, created_by=owner, priority="urgent",
        ).issue
        # The defect stays untyped and unclassified, exactly as the service leaves it.
        # Typing it would hide that coverage has to exclude defects itself.
        Issue.objects.filter(id=defect.id).update(state=states["completed"])
        record_test_result(
            run_case_id=current_cases["mark_false_happy"].id, project_id=project.id, status="passed",
            executed_by=owner,
            actual_result={"text": "修正後重驗:狀態即時更新,稽核紀錄含修正前後值。"},
            duration_ms=48000,
        )
        # The blocked writeback keeps a second defect open, so the gate has something
        # unresolved to report alongside the failing threshold.
        blocked = record_test_result(
            run_case_id=current_cases["writeback_mes"].id, project_id=project.id, status="blocked",
            executed_by=owner,
            actual_result={"text": "MES 測試環境回 503,無法驗證回寫。"},
            duration_ms=12000,
        )
        create_defect_from_result(
            result_id=blocked.id, run_case_id=current_cases["writeback_mes"].id,
            project_id=project.id, created_by=owner, priority="high",
        )
        return defect

    def _record_system_level_nfrs(self, workspace, project, owner):
        """System-level quality requirements, which are not test cases.

        Availability is last month's measurement, a scan belongs to the pipeline, and a
        sign-off is a decision. None can be executed before shipping, so they are
        recorded as release evidence and the gate reads them alongside run results.
        """
        for kind, key, name, status, detail, url in (
            ("slo", "availability-monthly", "可用性(上月)", "failing",
             "99.7%,低於 99.9% 目標", "https://grafana.internal/slo/trace-query"),
            ("slo", "rpo-rto", "災難復原演練", "passing", "RPO 12 分鐘 / RTO 1 小時 40 分,符合目標", ""),
            ("scan", "dependency-audit", "相依套件稽核", "passing", "0 個高風險漏洞", ""),
            ("scan", "tls-baseline", "傳輸加密基線", "passing", "全數端點為 TLS 1.3", ""),
            ("review", "arch-signoff", "架構審查簽核", "pending", "等待平台組簽核", ""),
        ):
            ReleaseEvidence.objects.create(
                project=project, workspace=workspace, kind=kind, key=key, name=name,
                status=status, detail=detail, source_url=url, created_by=owner,
            )

    def _report(self, project, workspace, items, cases, runs, defect):
        base = f"/{workspace.slug}/projects/{project.id}/testing"
        write = self.stdout.write
        write(self.style.SUCCESS(f"Seeded {project.identifier} ({project.id})"))
        write("")
        write("  Axis 1 -- work breakdown   2 epics / 3 features / 11 stories")
        write("  Axis 2 -- requirement kind functional and non-functional, set per work item")
        write("  Axis 3 -- sprint           2026-07B delivered, 2026-08A in flight, one story carried over")
        write("")
        write(f"  {len(cases)} contracts across functional, performance, reliability and security")
        write(f"  2 runs, each scoped to its cycle ({PREVIOUS_BUILD}, {CURRENT_BUILD})")
        write(f"  1 failure -> defect {project.identifier}-{defect.sequence_id} -> retest appended")
        write("  5 release-evidence records for the system-level quality requirements")
        write("")
        write("What the sample demonstrates:")
        write("  the three axes cross rather than nest -- an NFR story sits under a feature, in a sprint")
        write("  coverage rolls up, so features and epics report the contracts beneath them")
        write("  a scheduled story with no contract blocks the gate, and so does a failing SLO")
        write("  the closed sprint keeps the contract version it pinned, though the library moved on")
        write("  the threshold cases carry two measurements each, so a trend exists")
        write("")
        write(f"  overview  {base}/overview")
        write(f"  cases     {base}/cases")
        write(f"  runs      {base}/runs")
