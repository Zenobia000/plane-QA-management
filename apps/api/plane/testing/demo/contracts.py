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
    ("order_happy", "order_query"),
    ("order_notfound", "order_query"),
    ("api_contract", "order_query"),
    ("shipment_happy", "shipment_query"),
    ("export_csv", "export"),
    ("query_p95", "query_latency"),
    ("mark_false_happy", "mark_false"),
    ("mark_false_audit", "mark_false"),
    ("writeback_payment", "writeback"),
    ("cross_region", "authorization"),
    ("notify_visible", "notify_latency"),
    ("notify_failure_rate", "notify_failure"),
)

# case key -> (source, external id)
AUTOMATION_LINKS = (
    ("api_contract", "pytest", "tests/contract/test_order_history_api.py::test_query_by_order_number"),
    ("notify_visible", "pytest", "tests/e2e/test_notification.py::test_delivered_within_5s"),
    ("query_p95", "k6", "k6/order-history-p95"),
    ("notify_failure_rate", "prometheus", "notification_error_rate_24h"),
)


def create_folders(project):
    root = create_test_folder(project_id=project.id, name="訂單服務", sort_order=1000)
    return {
        "query": create_test_folder(project_id=project.id, name="歷程查詢", parent_id=root.id, sort_order=1000),
        "review": create_test_folder(project_id=project.id, name="退貨審核", parent_id=root.id, sort_order=2000),
        "quality": create_test_folder(project_id=project.id, name="品質門檻", parent_id=root.id, sort_order=3000),
        "notify": create_test_folder(project_id=project.id, name="通知服務", parent_id=root.id, sort_order=4000),
    }


def _functional_cases(project, folders):
    def case(title, folder, tags, steps, priority="high", preconditions=None):
        return create_test_case(
            project_id=project.id, title=title, folder_id=folders[folder].id, priority=priority,
            case_type="functional", tags=tags, preconditions=preconditions or {}, steps=steps,
        )

    return {
        "order_happy": case(
            "以有效訂單編號查詢可顯示完整處理歷程", "query", ["functional", "manual", "smoke"],
            [
                _step("輸入訂單編號 SO-20260728-001 並查詢", "顯示該訂單經歷的所有處理階段"),
                _step("檢視階段列表", "每個階段顯示進入與完成時間"),
                _step("展開任一階段", "顯示系統判定結果與人工更正紀錄"),
            ],
            preconditions={"text": "訂單 SO-20260728-001 已存在,使用者具 TW 區域權限"},
        ),
        "order_notfound": case(
            "查詢不存在的訂單應顯示明確訊息", "query", ["functional", "manual", "negative"],
            [_step("輸入不存在的訂單編號並查詢", "顯示查無資料訊息,不出現錯誤畫面")], priority="medium",
        ),
        "shipment_happy": case(
            "以物流單號查詢可顯示該筆配送歷程", "query", ["functional", "manual"],
            [_step("輸入物流單號 LG-A1B2C3 並查詢", "顯示該單號的完整配送歷程")],
            preconditions={"text": "物流單號 LG-A1B2C3 已完成三個配送階段"},
        ),
        "export_csv": case(
            "歷程可匯出為對帳用 CSV", "query", ["functional", "manual"],
            [
                _step("在歷程頁選擇匯出", "產生 CSV 下載"),
                _step("開啟 CSV", "欄位含訂單、物流單號、階段、進入與完成時間、判定結果、更正者"),
            ],
            priority="medium",
        ),
        "mark_false_happy": case(
            "客服可將誤擋的退貨標記為誤判", "review", ["functional", "manual"],
            [
                _step("開啟該退貨申請並選擇標記為誤判", "顯示原因輸入欄位"),
                _step("填寫原因並送出", "申請狀態變更為已更正並記錄更正者"),
            ],
            preconditions={"text": "存在一筆系統判定為退貨不成立的申請"},
        ),
        "mark_false_audit": case(
            "更正操作必須留下稽核紀錄", "review", ["functional", "manual", "negative"],
            [_step("完成一次誤判更正後檢視稽核紀錄", "紀錄含操作者、時間、更正前後值")], priority="medium",
        ),
        "writeback_payment": case(
            "審核通過的更正 30 秒內回寫金流系統", "review", ["functional", "manual"],
            [
                _step("主管審核通過一筆更正", "顯示已送出回寫"),
                _step("查詢金流系統對應訂單", "30 秒內可見更新後的判定結果"),
            ],
        ),
        "notify_visible": case(
            "事件發生後 5 秒內使用者可見通知", "notify", ["functional", "automated"],
            [_step("觸發一次狀態變更並輪詢通知列表", "5 秒內通知列表顯示該筆通知")], priority="medium",
        ),
        "api_contract": case(
            "歷程查詢 API 在有效請求下回應 200", "query", ["functional", "automated"],
            [_step("GET /api/orders/SO-20260728-001/history", "回應 200 且 payload 含 stages 陣列")],
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
        project_id=project.id, title="歷程查詢 P95 回應時間低於 2,000 ms",
        folder_id=folders["quality"].id, priority="high", case_type="performance",
        tags=["performance", "automated", "threshold"],
        preconditions={
            "text": "資料庫含 1,000 萬筆歷程 · 200 VU · 持續 5 分鐘",
            "dataset_rows": 10_000_000,
            "vus": 200,
        },
        steps=[{
            "action": {"text": "以隨機有效訂單編號持續發送查詢請求", "tool": "k6"},
            "expected_result": {
                "text": "P95 回應時間 < 2,000 ms", "metric": "http_req_duration_p95",
                "operator": "<", "threshold": 2000, "unit": "ms",
            },
        }],
    )
    cases["notify_failure_rate"] = create_test_case(
        project_id=project.id, title="通知服務 24 小時失敗率低於 0.5%",
        folder_id=folders["quality"].id, priority="high", case_type="reliability",
        tags=["reliability", "automated", "threshold"],
        preconditions={"text": "取樣連續 24 小時的通知發送", "window_hours": 24},
        steps=[{
            "action": {"text": "統計通知發送的失敗比例", "tool": "prometheus"},
            "expected_result": {
                "text": "失敗率 < 0.5%", "metric": "notification_error_rate",
                "operator": "<", "threshold": 0.5, "unit": "%",
            },
        }],
    )
    cases["cross_region"] = create_test_case(
        project_id=project.id, title="跨區域查詢應被拒絕並留下稽核紀錄",
        folder_id=folders["quality"].id, priority="urgent", case_type="security",
        tags=["security", "manual", "negative"],
        preconditions={"text": "使用者僅具 TW 區域權限;訂單 SO-20260728-999 屬於 JP"},
        steps=[
            _step("以 TW 使用者查詢 JP 的訂單", "系統拒絕提供資料"),
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
