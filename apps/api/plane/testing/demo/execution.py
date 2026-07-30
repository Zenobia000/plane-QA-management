# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Two sprints of verification, and the loop that closes back into the backlog.

Each run binds to the cycle that commissioned it. A run without that binding cannot be
reported against its sprint, which is how planning and execution quietly drift apart --
the sprint closes, the run stays open, and nobody can say afterwards which build the
sprint was signed off on.

Two runs also give each threshold contract a second measurement, so the demo carries a
trend rather than a single reading. One measurement is a fact; two are a direction.
"""

# Module imports
from plane.db.models import Issue
from plane.testing.services import (
    create_defect_from_result,
    create_fixed_test_run,
    publish_test_case_version,
    record_test_result,
)

PREVIOUS_BUILD = "2026.07.c1a8e42"
CURRENT_BUILD = "2026.08.b7d40e1"

PREVIOUS_KEYS = ["order_happy", "order_notfound", "shipment_happy", "api_contract", "query_p95"]
CURRENT_KEYS = [
    "order_happy", "shipment_happy", "export_csv", "mark_false_happy", "mark_false_audit",
    "writeback_payment", "cross_region", "notify_visible", "api_contract",
    "query_p95", "notify_failure_rate",
]


def _step(action, expected):
    return {"action": {"text": action}, "expected_result": {"text": expected}}


def _run_cases(run, cases, keys):
    by_case = {run_case.test_case_id: run_case for run_case in run.run_cases.all()}
    return {key: by_case[cases[key].id] for key in keys}


def _previous_sprint(project, owner, cases, modules, cycles):
    run = create_fixed_test_run(
        project_id=project.id,
        name="Sprint 2026-07B 回歸驗證",
        test_case_ids=[cases[key].id for key in PREVIOUS_KEYS],
        build=PREVIOUS_BUILD,
        cycle_id=cycles["previous"].id,
        module_id=modules["訂單查詢"].id,
        description={"text": "上一期交付的查詢功能與效能門檻。"},
    )
    run_cases = _run_cases(run, cases, PREVIOUS_KEYS)

    for key, actual, duration in (
        ("order_happy", "三個處理階段皆正確顯示,含判定結果與更正紀錄。", 38000),
        ("order_notfound", "顯示查無資料,無錯誤畫面。", 9000),
        ("shipment_happy", "配送歷程完整。", 27000),
        ("api_contract", "CI:200,stages 長度 3。", 240),
    ):
        record_test_result(
            run_case_id=run_cases[key].id, project_id=project.id, status="passed",
            executed_by=owner, actual_result={"text": actual}, duration_ms=duration,
        )
    record_test_result(
        run_case_id=run_cases["query_p95"].id, project_id=project.id, status="passed",
        executed_by=owner,
        actual_result={
            "text": "P95 1,910 ms(門檻 2,000 ms)", "measured": 1910, "unit": "ms",
            "metric": "http_req_duration_p95", "source": "k6 · CI run #451",
        },
        duration_ms=300000,
    )
    return run, run_cases


def _amend_a_pinned_contract(project, cases):
    """Editing a contract after a run has pinned it.

    This is the invariant worth seeing rather than reading about: the closed sprint keeps
    executing the version it saw, while the library moves on. Version four exists from
    here forward; run 2026-07B still reports against version one.
    """
    publish_test_case_version(
        test_case_id=cases["order_happy"].id, project_id=project.id,
        title="以有效訂單編號查詢可顯示完整處理歷程", priority="high",
        case_type="functional", tags=["functional", "manual", "smoke"],
        preconditions={"text": "訂單 SO-20260728-001 已存在,使用者具 TW 區域權限;瀏覽器語系為繁體中文"},
        steps=[
            _step("輸入訂單編號 SO-20260728-001 並查詢", "顯示該訂單經歷的所有處理階段"),
            _step("檢視階段列表", "每個階段顯示進入與完成時間"),
            _step("展開任一階段", "顯示系統判定結果與人工更正紀錄"),
            _step("切換語系為英文", "階段名稱與狀態皆已翻譯"),
        ],
    )


def _current_sprint(project, owner, cases, modules, cycles):
    run = create_fixed_test_run(
        project_id=project.id,
        name="Sprint 2026-08A 回歸驗證",
        test_case_ids=[cases[key].id for key in CURRENT_KEYS],
        build=CURRENT_BUILD,
        cycle_id=cycles["current"].id,
        module_id=modules["訂單查詢"].id,
        description={"text": "本期的退貨更正與回寫,加上前期功能的回歸。"},
    )
    run_cases = _run_cases(run, cases, CURRENT_KEYS)

    for key, actual, duration in (
        ("order_happy", "回歸通過,語系切換後階段名稱正確。", 41000),
        ("shipment_happy", "配送歷程完整。", 26000),
        ("mark_false_audit", "稽核紀錄含操作者、時間與前後值。", 15000),
        ("cross_region", "跨區域查詢被拒,稽核紀錄已產生。", 31000),
        ("api_contract", "CI:200,stages 長度 3。", 230),
        ("notify_visible", "CI:平均 3.2 秒送達。", 3200),
    ):
        record_test_result(
            run_case_id=run_cases[key].id, project_id=project.id, status="passed",
            executed_by=owner, actual_result={"text": actual}, duration_ms=duration,
        )
    record_test_result(
        run_case_id=run_cases["query_p95"].id, project_id=project.id, status="passed",
        executed_by=owner,
        actual_result={
            "text": "P95 1,840 ms(門檻 2,000 ms,較上期改善 70 ms)", "measured": 1840, "unit": "ms",
            "metric": "http_req_duration_p95", "source": "k6 · CI run #482",
        },
        duration_ms=300000,
    )
    # A threshold that misses is still a passing-shaped measurement until someone compares
    # it, which is why the status is recorded as failed explicitly rather than inferred.
    record_test_result(
        run_case_id=run_cases["notify_failure_rate"].id, project_id=project.id, status="failed",
        executed_by=owner,
        actual_result={
            "text": "失敗率 0.8%,超出 0.5% 門檻", "measured": 0.8, "unit": "%",
            "metric": "notification_error_rate", "source": "prometheus · 24h window",
        },
        duration_ms=86400000,
    )
    record_test_result(
        run_case_id=run_cases["export_csv"].id, project_id=project.id, status="blocked",
        executed_by=owner,
        actual_result={"text": "匯出欄位規格尚未定案,無法驗證;此故事自上期順延。"},
        duration_ms=6000,
    )
    return run, run_cases


def execute(project, owner, cases, modules, cycles):
    previous = _previous_sprint(project, owner, cases, modules, cycles)
    _amend_a_pinned_contract(project, cases)
    current = _current_sprint(project, owner, cases, modules, cycles)
    return {"previous": previous, "current": current}


def close_the_loop(project, owner, runs, states):
    """Failure to defect to fix to retest, without overwriting anything.

    The retest is a new result appended beside the failure, not a correction of it. That
    is what makes the history readable afterwards: the sequence shows the case failed, a
    defect was raised, and a later execution passed -- rather than showing a case that was
    always green.
    """
    _current, current_cases = runs["current"]
    failure = record_test_result(
        run_case_id=current_cases["mark_false_happy"].id, project_id=project.id, status="failed",
        executed_by=owner,
        actual_result={"text": "送出更正後狀態未更新,重整才看得到變更;稽核紀錄缺少更正前值。"},
        duration_ms=52000,
    )
    defect = create_defect_from_result(
        result_id=failure.id, run_case_id=current_cases["mark_false_happy"].id,
        project_id=project.id, created_by=owner, priority="urgent",
    ).issue
    # The defect stays untyped and unclassified, exactly as the service leaves it. Typing
    # it would hide that the coverage report has to exclude defects itself.
    Issue.objects.filter(id=defect.id).update(state=states["completed"])
    record_test_result(
        run_case_id=current_cases["mark_false_happy"].id, project_id=project.id, status="passed",
        executed_by=owner,
        actual_result={"text": "更正後重驗:狀態即時更新,稽核紀錄含更正前後值。"},
        duration_ms=48000,
    )
    # The blocked write-back keeps a second defect open, so the gate has something
    # unresolved to report alongside the failing threshold.
    blocked = record_test_result(
        run_case_id=current_cases["writeback_payment"].id, project_id=project.id, status="blocked",
        executed_by=owner,
        actual_result={"text": "金流測試環境回 503,無法驗證回寫。"},
        duration_ms=12000,
    )
    create_defect_from_result(
        result_id=blocked.id, run_case_id=current_cases["writeback_payment"].id,
        project_id=project.id, created_by=owner, priority="high",
    )
    return defect
