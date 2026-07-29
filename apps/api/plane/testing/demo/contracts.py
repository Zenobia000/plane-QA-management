# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Acceptance contracts, and where they attach.

Every case here is created through `plane.testing.services`, never through the ORM
directly, so the four invariants hold on seeded data exactly as they do on real data:
editing publishes a new immutable version, a run pins the version it saw, results only
ever append, and a defect can only be born from a failed or blocked result.

Contracts link to stories, never to features or epics. Acceptance is decided at story
level, and the coverage report inherits upward from there -- so a feature reporting
"covered" is reporting about the stories beneath it, not about a link of its own.
"""

# Module imports
from plane.db.models import TestCaseAutomationLink
from plane.testing.services import create_test_case, create_test_folder, link_test_case_to_work_item


def _step(action, expected):
    return {"action": {"text": action}, "expected_result": {"text": expected}}


# case key -> work item key
CONTRACT_LINKS = (
    ("wo_happy", "wo_query"),
    ("wo_notfound", "wo_query"),
    ("api_contract", "wo_query"),
    ("sn_happy", "sn_query"),
    ("export_csv", "export"),
    ("query_p95", "query_latency"),
    ("mark_false_happy", "mark_false"),
    ("mark_false_audit", "mark_false"),
    ("writeback_mes", "writeback"),
    ("cross_site", "authorization"),
    ("inference_visible", "inference_latency"),
    ("inference_failure_rate", "inference_failure"),
)

# case key -> (source, external id)
AUTOMATION_LINKS = (
    ("api_contract", "pytest", "tests/contract/test_trace_api.py::test_query_by_work_order"),
    ("inference_visible", "pytest", "tests/e2e/test_inference.py::test_result_visible_within_5s"),
    ("query_p95", "k6", "k6/trace-query-p95"),
    ("inference_failure_rate", "prometheus", "inference_error_rate_24h"),
)


def create_folders(project):
    root = create_test_folder(project_id=project.id, name="生產履歷", sort_order=1000)
    return {
        "query": create_test_folder(project_id=project.id, name="履歷查詢", parent_id=root.id, sort_order=1000),
        "review": create_test_folder(project_id=project.id, name="NG 修正", parent_id=root.id, sort_order=2000),
        "quality": create_test_folder(project_id=project.id, name="品質門檻", parent_id=root.id, sort_order=3000),
        "inference": create_test_folder(project_id=project.id, name="AI 推論", parent_id=root.id, sort_order=4000),
    }


def _functional_cases(project, folders):
    def case(title, folder, tags, steps, priority="high", preconditions=None):
        return create_test_case(
            project_id=project.id, title=title, folder_id=folders[folder].id, priority=priority,
            case_type="functional", tags=tags, preconditions=preconditions or {}, steps=steps,
        )

    return {
        "wo_happy": case(
            "以有效工單編號查詢可顯示完整站點履歷", "query", ["functional", "manual", "smoke"],
            [
                _step("輸入工單編號 WO-20260728-001 並查詢", "顯示該工單經歷的所有工站"),
                _step("檢視站點列表", "每站顯示進站與離站時間"),
                _step("展開任一工站", "顯示 AI 推論結果與人工修正紀錄"),
            ],
            preconditions={"text": "工單 WO-20260728-001 已存在,使用者具 CN21 廠區權限"},
        ),
        "wo_notfound": case(
            "查詢不存在的工單應顯示明確訊息", "query", ["functional", "manual", "negative"],
            [_step("輸入不存在的工單編號並查詢", "顯示查無資料訊息,不出現錯誤畫面")], priority="medium",
        ),
        "sn_happy": case(
            "以產品序號查詢可顯示該件產品履歷", "query", ["functional", "manual"],
            [_step("輸入產品序號 SN-A1B2C3 並查詢", "顯示該序號的完整站點履歷")],
            preconditions={"text": "序號 SN-A1B2C3 已完成三個工站"},
        ),
        "export_csv": case(
            "履歷可匯出為稽核用 CSV", "query", ["functional", "manual"],
            [
                _step("在履歷頁選擇匯出", "產生 CSV 下載"),
                _step("開啟 CSV", "欄位含工單、序號、工站、進出站時間、推論結果、修正者"),
            ],
            priority="medium",
        ),
        "mark_false_happy": case(
            "IE 可將誤判 NG 標記為誤報", "review", ["functional", "manual"],
            [
                _step("開啟該 NG 事件並選擇標記為誤報", "顯示原因輸入欄位"),
                _step("填寫原因並送出", "事件狀態變更為已修正並記錄修正者"),
            ],
            preconditions={"text": "存在一筆 AI 判定為 NG 的事件"},
        ),
        "mark_false_audit": case(
            "修正操作必須留下稽核紀錄", "review", ["functional", "manual", "negative"],
            [_step("完成一次誤報修正後檢視稽核紀錄", "紀錄含操作者、時間、修正前後值")], priority="medium",
        ),
        "writeback_mes": case(
            "審核通過的修正 30 秒內回寫 MES", "review", ["functional", "manual"],
            [
                _step("主管審核通過一筆修正", "顯示已送出回寫"),
                _step("查詢 MES 對應工單", "30 秒內可見更新後的判定結果"),
            ],
        ),
        "inference_visible": case(
            "推論完成後 5 秒內工單可見結果", "inference", ["functional", "automated"],
            [_step("送出一張待推論影像並輪詢工單", "5 秒內工單顯示推論結果")], priority="medium",
        ),
        "api_contract": case(
            "履歷查詢 API 在有效請求下回應 200", "query", ["functional", "automated"],
            [_step("GET /api/trace?wo=WO-20260728-001", "回應 200 且 payload 含 stations 陣列")],
            priority="medium",
        ),
    }


def _threshold_cases(project, folders):
    """Non-functional contracts whose expectation is structured rather than prose.

    A threshold written as a sentence can be read but not judged and not charted. Splitting
    it into metric, operator, threshold and unit is what lets the result carry a measured
    value beside it, and two runs then make a trend rather than two opinions.
    """
    cases = {}
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
    return cases


def create_contracts(project, items):
    folders = create_folders(project)
    cases = _functional_cases(project, folders)
    cases.update(_threshold_cases(project, folders))

    for case_key, item_key in CONTRACT_LINKS:
        link_test_case_to_work_item(
            test_case_id=cases[case_key].id, issue_id=items[item_key].id, project_id=project.id
        )
    return folders, cases


def create_automation_links(project, cases, owner):
    """The stable identity CI uploads map onto.

    Without this row a pipeline result has nothing to attach to, so ingestion creates a
    fresh orphan case on every run and the same assertion accumulates a new contract each
    night. `external_id` is the contract between the test runner's naming and this library;
    it is why renaming a test function is a traceability decision, not a refactor.
    """
    for case_key, source, external_id in AUTOMATION_LINKS:
        TestCaseAutomationLink.objects.create(
            project=project,
            workspace=project.workspace,
            test_case=cases[case_key],
            source=source,
            external_id=external_id,
            created_by=owner,
        )
