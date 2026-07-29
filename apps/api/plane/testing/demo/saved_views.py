# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Saved views: a stored question about the backlog.

A view is a filter plus a layout, saved so a recurring question stops being retyped. It
is worth being precise about what that does and does not make it:

- a view **is** a lens over work items, recomputed on every read
- a view **is not** a container. Nothing belongs to a view, and deleting one loses no data
- a view **cannot** reach the testing axis. Coverage, run status and release-gate blockers
  are not work-item fields, so no filter expresses "requirements with no contract"

That last limit is the useful one to internalise. `issue_filters` accepts state, priority,
labels, assignees, cycle, module, estimate point, target date, parent and type -- the
breakdown and scheduling axes, and nothing from verification or evidence. The quality
questions are answered by `quality_coverage` and `quality_release_gate` instead, which is
why the demo ships both and does not pretend one substitutes for the other.

Two further limits are worth knowing before designing around them:

- work-item **properties** are not filterable. "Show me every non-functional requirement"
  cannot be a view today, even though requirement kind is a first-class property. Views
  read labels, not properties
- **absence** is not expressible. `assignees: ["null"]` reaches the ORM as a literal string
  and raises on UUID coercion, so "scheduled but unassigned" -- a question worth asking at
  every planning meeting -- has no saved-view form. Filters select by value, not by
  emptiness

Both limits push the same way: a view answers "which items match these values", and
anything phrased as "which items are missing something" belongs in a report instead.
"""

# Module imports
from plane.db.models import IssueView

DISPLAY_PROPERTIES = {
    "assignee": True,
    "attachment_count": False,
    "created_on": False,
    "due_date": True,
    "estimate": True,
    "key": True,
    "labels": True,
    "link": True,
    "priority": True,
    "start_date": False,
    "state": True,
    "sub_issue_count": True,
    "updated_on": False,
}


def _display(group_by=None, order_by="-created_at", layout="list"):
    return {
        "group_by": group_by,
        "order_by": order_by,
        "type": None,
        "sub_issue": True,
        "show_empty_groups": True,
        "layout": layout,
        "calendar_date_range": "",
    }


def _view(workspace, owner, name, description, filters, display, project=None):
    return IssueView.objects.create(
        workspace=workspace,
        project=project,
        name=name,
        description=description,
        filters=filters,
        display_filters=display,
        display_properties=DISPLAY_PROPERTIES,
        access=1,
        owned_by=owner,
        created_by=owner,
    )


def create_views(workspace, project, owner, context):
    """Six project views and one workspace view, each answering a standing question.

    They are grouped by which axis the filter reads, because that is the thing a reader
    should take away: every one of these is a question about the breakdown or the schedule.
    None of them is a question about quality, and no arrangement of filters would make one.
    """
    labels = context["labels"]
    cycles = context["cycles"]
    points = context["points"]
    views = {}

    # --- Scheduling axis: what is in flight, and what shipped ---
    views["current_sprint"] = _view(
        workspace, owner,
        "本期進行中",
        "Sprint 2026-08A 內尚未完成的項目。每日站立會的預設視角。",
        {"cycle": [str(cycles["current"].id)], "state_group": ["backlog", "unstarted", "started"]},
        _display(group_by="state", order_by="-priority"),
        project=project,
    )
    views["previous_delivered"] = _view(
        workspace, owner,
        "上期已交付",
        "Sprint 2026-07B 已完成的項目,回顧與驗收證據的入口。",
        {"cycle": [str(cycles["previous"].id)], "state_group": ["completed"]},
        _display(group_by="module"),
        project=project,
    )

    # --- Breakdown axis: risk and ownership ---
    views["urgent_open"] = _view(
        workspace, owner,
        "高優先未完成",
        "urgent 與 high 且尚未完成。排序用,不是狀態報告。",
        {"priority": ["urgent", "high"], "state_group": ["backlog", "unstarted", "started"]},
        _display(group_by="priority", order_by="target_date"),
        project=project,
    )
    views["inference_module"] = _view(
        workspace, owner,
        "AI 推論服務(模組)",
        "依模組切,而非依 sprint 或 epic。同一個模組的項目散落在不同 epic 與不同 sprint 裡,"
        "這正是模組不是階層的證據。",
        {"module": [str(context["modules"]["AI 推論服務"].id)]},
        _display(group_by="state"),
        project=project,
    )
    views["large_stories"] = _view(
        workspace, owner,
        "點數過大的故事",
        "8 點以上。拆票的候選清單 —— 一張票大到估不準,通常是還沒想清楚。",
        {"estimate_point": [str(points["8"].id), str(points["13"].id)]},
        _display(group_by="state"),
        project=project,
    )

    # --- Label axis: cross-cutting obligations ---
    views["audit_scope"] = _view(
        workspace, owner,
        "法規稽核範圍",
        "帶有「法規稽核」標籤的項目,其驗收紀錄需保留供調閱。示範標籤如何橫切三個軸。",
        {"labels": [str(labels["法規稽核"].id)]},
        _display(group_by="state"),
        project=project,
    )

    # --- Workspace scope: the same question across projects ---
    views["cross_project_urgent"] = _view(
        workspace, owner,
        "跨專案:urgent 未完成",
        "workspace 層視角,不綁任何專案。示範 view 可以跨越專案邊界,而 cycle 與 module 不行。",
        {"priority": ["urgent"], "state_group": ["backlog", "unstarted", "started"]},
        _display(group_by="project"),
        project=None,
    )

    return views
