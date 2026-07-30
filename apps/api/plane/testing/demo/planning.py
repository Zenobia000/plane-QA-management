# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The work breakdown, and the three independent ways of scheduling it.

The breakdown is a tree: initiative, epic, feature, story, each holding the next through
`parent`. Scheduling is not a tree at all. Sprint, module and milestone are three
cross-sections carried by join tables and a foreign key, and a single story sits in all
three at once without any of them containing another. Reading the diagram in
`docs/process/plane-qa-guideline.md` B0 alongside this file is the fastest way to see it.

Relations are the fourth thing, and the one most often confused with the breakdown. A
parent contains its children; a relation connects peers. "Write-back is blocked by
marking" is not a hierarchy statement -- neither story owns the other, and either can
move to a different feature without the dependency changing.
"""

# Python imports
import datetime

# Django imports
from django.utils import timezone

# Module imports
from plane.db.models import (
    Cycle,
    CycleIssue,
    Initiative,
    InitiativeProject,
    Issue,
    IssueAssignee,
    IssueComment,
    IssueLabel,
    IssueLink,
    IssueRelation,
    Module,
    ModuleIssue,
    WorkItemPropertyValue,
)

MODULE_NAMES = ("訂單查詢", "通知服務")


def _as_datetime(day):
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time.min))


def create_initiative(workspace, project, owner):
    """The top of the breakdown, and the only level that lives above a project.

    An initiative is workspace-scoped and joins projects through a membership table, so
    one strategic outcome can span several teams' projects. That M:N shape is why it
    cannot simply be another epic: an epic belongs to exactly one project.
    """
    initiative = Initiative.objects.create(
        workspace=workspace,
        name="訂單體驗數位化",
        description=(
            "把訂單查詢與退貨處理從人工客服轉為可追溯的自助流程。跨專案:本專案負責歷程與退貨審核,"
            "金流整合由另一個專案承接。"
        ),
        status="in_progress",
        target_date=timezone.now().date() + datetime.timedelta(days=120),
        created_by=owner,
    )
    InitiativeProject.objects.create(
        initiative=initiative, project=project, workspace=workspace, created_by=owner
    )
    return initiative


def create_schedule(workspace, project, owner):
    """Modules and sprints. Milestones are created in scaffolding, before any work item."""
    modules = {
        name: Module.objects.create(workspace=workspace, project=project, name=name, created_by=owner, lead=owner)
        for name in MODULE_NAMES
    }
    today = timezone.now().date()
    cycles = {
        "previous": Cycle.objects.create(
            workspace=workspace,
            project=project,
            name="Sprint 2026-07B",
            start_date=_as_datetime(today - datetime.timedelta(days=18)),
            end_date=_as_datetime(today - datetime.timedelta(days=5)),
            owned_by=owner,
            created_by=owner,
        ),
        "current": Cycle.objects.create(
            workspace=workspace,
            project=project,
            name="Sprint 2026-08A",
            start_date=_as_datetime(today - datetime.timedelta(days=4)),
            end_date=_as_datetime(today + datetime.timedelta(days=10)),
            owned_by=owner,
            created_by=owner,
        ),
    }
    return modules, cycles


class _ItemBuilder:
    """Assembles one work item across every axis it participates in."""

    def __init__(self, workspace, project, owner, context):
        self.workspace = workspace
        self.project = project
        self.owner = owner
        self.types = context["types"]
        self.states = context["states"]
        self.modules = context["modules"]
        self.cycles = context["cycles"]
        self.labels = context["labels"]
        self.points = context["points"]
        self.milestones = context["milestones"]
        self.properties = context["properties"]
        self.options = {
            name: {option.value: option for option in prop.options.all()}
            for name, prop in self.properties.items()
        }

    def _set_property(self, issue, name, value):
        # Keyed by option value, so membership has to be tested against the value being
        # stored -- not against the property name, which is never an option.
        options = self.options.get(name) or {}
        if isinstance(value, list):
            stored = [{"value": item, "label": options[item].label} for item in value]
        elif isinstance(value, str) and value in options:
            stored = {"value": value, "label": options[value].label}
        else:
            stored = {"value": value}
        WorkItemPropertyValue.objects.create(
            project=self.project,
            workspace=self.workspace,
            property=self.properties[name],
            issue=issue,
            value=stored,
            created_by=self.owner,
        )

    def build(
        self,
        name,
        description,
        level,
        state,
        kind,
        parent=None,
        cycle=None,
        module=None,
        milestone=None,
        priority="high",
        labels=(),
        points=None,
        regions=("TW",),
        audited=False,
        services=None,
        promised_in=None,
        assign=True,
    ):
        issue = Issue.objects.create(
            workspace=self.workspace,
            project=self.project,
            name=name,
            description_html=f"<p>{description}</p>",
            state=self.states[state],
            priority=priority,
            type=self.types[level],
            parent=parent,
            milestone=self.milestones[milestone] if milestone else None,
            estimate_point=self.points[points] if points else None,
            created_by=self.owner,
            start_date=self.cycles["previous"].start_date.date() if cycle == "previous" else None,
            target_date=self.cycles[cycle].end_date.date() if cycle else None,
        )

        self._set_property(issue, "Requirement kind", kind)
        self._set_property(issue, "目標區域", list(regions))
        self._set_property(issue, "需法規稽核", audited)
        if services is not None:
            self._set_property(issue, "影響服務數", services)
        if promised_in is not None:
            self._set_property(
                issue,
                "客戶承諾日",
                (timezone.now().date() + datetime.timedelta(days=promised_in)).isoformat(),
            )

        if cycle:
            CycleIssue.objects.create(
                workspace=self.workspace, project=self.project, cycle=self.cycles[cycle], issue=issue,
                created_by=self.owner,
            )
        if module:
            ModuleIssue.objects.create(
                workspace=self.workspace, project=self.project, module=self.modules[module], issue=issue,
                created_by=self.owner,
            )
        for label in labels:
            IssueLabel.objects.create(
                workspace=self.workspace, project=self.project, issue=issue, label=self.labels[label],
                created_by=self.owner,
            )
        if assign:
            IssueAssignee.objects.create(
                workspace=self.workspace, project=self.project, issue=issue, assignee=self.owner,
                created_by=self.owner,
            )
        return issue


def create_hierarchy(workspace, project, owner, context):
    """Every axis set at once, so no two can be inferred from each other.

    Read any story below and note that its parent, its sprint, its module, its milestone,
    its requirement kind and its labels are six independent facts. `query_latency` is a
    non-functional requirement, under a functional feature, in the delivered sprint,
    against the completed milestone -- a combination no single hierarchy could express.
    """
    builder = _ItemBuilder(workspace, project, owner, context)
    item = builder.build

    trace = item(
        "訂單歷程與退貨追溯能力", "讓客服能追查任一筆訂單在各處理階段的結果與異常紀錄。",
        "Epic", "In progress", "functional", module="訂單查詢", regions=("TW", "JP"),
        audited=True, labels=("法規稽核",),
    )
    notify = item(
        "通知服務可靠性", "通知必須及時、穩定地送達使用者,否則客服失去溝通依據。",
        "Epic", "In progress", "non_functional", module="通知服務", regions=("TW", "JP", "SEA"),
    )
    query = item(
        "訂單與物流單號查詢", "支援以訂單編號或物流單號查詢完整處理歷程。",
        "Feature", "In progress", "functional", parent=trace, module="訂單查詢",
        milestone="M1 訂單查詢上線", regions=("TW", "JP"), audited=True,
    )
    review = item(
        "退貨申請與審核", "客服可更正誤擋的退貨,主管審核後回寫金流系統。",
        "Feature", "In progress", "functional", parent=trace, module="訂單查詢",
        milestone="M2 退貨審核與回寫", labels=("跨團隊相依",),
    )
    latency = item(
        "通知送達即時性", "事件發生到使用者收到通知的延遲必須可控。",
        "Feature", "In progress", "non_functional", parent=notify, module="通知服務",
    )

    items = {
        "epic_trace": trace,
        "epic_notify": notify,
        "feature_query": query,
        "feature_review": review,
        "feature_latency": latency,
        # --- Sprint 2026-07B, delivered ---
        "order_query": item(
            "客服以訂單編號查詢處理歷程", "輸入訂單編號後顯示各處理階段的進入與完成時間與系統判定結果。",
            "Story", "Done", "functional", parent=query, cycle="previous", module="訂單查詢",
            milestone="M1 訂單查詢上線", points="5", regions=("TW", "JP"), audited=True, services=6,
            labels=("法規稽核",),
        ),
        "shipment_query": item(
            "客服以物流單號查詢處理歷程", "輸入物流單號後顯示該筆配送的完整歷程。",
            "Story", "Done", "functional", parent=query, cycle="previous", module="訂單查詢",
            milestone="M1 訂單查詢上線", points="3", services=6,
        ),
        # A quality constraint on the query feature. It is a story-shaped unit of work in
        # its own sprint, and non-functional -- the two axes are independent.
        "query_latency": item(
            "歷程查詢 P95 回應時間低於 2 秒", "在 1,000 萬筆歷程資料下,查詢 API 的 P95 不得超過 2,000 ms。",
            "Story", "Done", "non_functional", parent=query, cycle="previous", module="訂單查詢",
            milestone="M1 訂單查詢上線", points="8", services=6,
        ),
        # --- Carried into Sprint 2026-08A ---
        "export": item(
            "歷程匯出為對帳報表", "自 Sprint 2026-07B 順延:匯出格式未定案,重新排入本期。",
            "Story", "In Design", "functional", parent=query, cycle="current", module="訂單查詢",
            milestone="M3 對帳報表與合規", priority="medium", points="5",
            audited=True, promised_in=45, services=6,
            labels=("上期順延", "需 UX 確認", "法規稽核"),
        ),
        # --- Sprint 2026-08A ---
        "mark_false": item(
            "客服將誤擋的退貨標記為誤判", "客服可將誤擋的退貨標記為誤判並填寫原因。",
            "Story", "In developing", "functional", parent=review, cycle="current", module="訂單查詢",
            milestone="M2 退貨審核與回寫", points="8", services=4,
        ),
        "writeback": item(
            "審核結果回寫金流系統", "審核通過的更正需在 30 秒內回寫金流系統。",
            "Story", "Pending", "functional", parent=review, cycle="current", module="訂單查詢",
            milestone="M2 退貨審核與回寫", points="13", services=4,
            labels=("跨團隊相依", "技術債"),
        ),
        # Scheduled into the sprint with no acceptance contract at all -- the
        # Definition-of-Ready violation the release gate has to catch.
        "supervisor": item(
            "主管審核退貨紀錄", "已排入本期卻未建立任何驗收契約,示範 Definition of Ready 違規。",
            "Story", "Todo", "functional", parent=review, cycle="current", module="訂單查詢",
            milestone="M2 退貨審核與回寫", priority="medium", points="5", assign=False,
        ),
        "authorization": item(
            "使用者僅能存取授權區域訂單", "跨區域查詢必須被拒絕並留下稽核紀錄。",
            "Story", "PR Reviewing", "non_functional", parent=review, cycle="current", module="訂單查詢",
            priority="urgent", points="5", regions=("TW", "JP", "SEA"), audited=True, services=12,
            labels=("法規稽核",),
        ),
        "notify_latency": item(
            "通知 5 秒內送達使用者", "事件發生後 5 秒內,使用者必須收到通知。",
            "Story", "In Diversity Testing", "functional", parent=latency, cycle="current", module="通知服務",
            points="8", services=12, promised_in=20, labels=("客戶承諾",),
        ),
        # A rolling 24-hour failure rate is re-measured every sprint and never reaches a
        # final state, which is what the `常駐維運` label records. The reference design
        # carried that as a workflow state; keeping it a label leaves the story free to move
        # through the same lifecycle as everything else while still being marked as work
        # that reserves capacity indefinitely.
        "notify_failure": item(
            "通知服務失敗率低於 0.5%", "連續 24 小時的通知發送失敗率不得超過 0.5%。",
            "Story", "Todo", "non_functional", parent=latency, cycle="current", module="通知服務",
            priority="medium", points="13", regions=("TW", "JP", "SEA"), services=12,
            labels=("常駐維運",),
        ),
    }
    return items


# (issue key, related key, relation type, why)
RELATIONS = (
    ("writeback", "mark_false", "blocked_by", "沒有標記誤判的動作,就沒有可回寫的更正。"),
    ("supervisor", "mark_false", "blocked_by", "審核的對象是更正紀錄,更正先於審核。"),
    ("notify_failure", "notify_latency", "relates_to", "同一個通知服務的兩種品質面向。"),
    ("export", "authorization", "relates_to", "匯出必須沿用查詢的區域授權規則。"),
)


def create_relations(workspace, project, owner, items):
    """Peer dependencies, which the breakdown cannot express.

    `writeback` and `mark_false` are siblings under the same feature, so the tree says
    nothing about their order. The dependency is a separate edge, and it survives either
    story being re-parented.
    """
    for issue_key, related_key, relation_type, _why in RELATIONS:
        IssueRelation.objects.create(
            workspace=workspace,
            project=project,
            issue=items[issue_key],
            related_issue=items[related_key],
            relation_type=relation_type,
            created_by=owner,
        )


# (issue key, title, url)
EXTERNAL_LINKS = (
    ("query_latency", "k6 負載測試腳本", "https://git.internal/quality/k6/order-history-p95.js"),
    ("query_latency", "Grafana:查詢延遲", "https://grafana.internal/d/order-query-latency"),
    ("notify_failure", "Grafana:通知失敗率", "https://grafana.internal/d/notification-error-rate"),
    ("export", "對帳報表欄位規格(草稿)", "https://wiki.internal/quality/reconciliation-export-spec"),
    ("authorization", "區域授權矩陣", "https://wiki.internal/security/region-authorization"),
)


def create_external_links(workspace, project, owner, items):
    """Pointers to evidence that lives outside Plane.

    A dashboard URL is not a test result. It is where a human goes to check something the
    system cannot execute, which is the same reason continuous-SLO requirements end up as
    release evidence rather than test cases.
    """
    for issue_key, title, url in EXTERNAL_LINKS:
        IssueLink.objects.create(
            workspace=workspace, project=project, issue=items[issue_key], title=title, url=url,
            created_by=owner,
        )


# (issue key, comment)
COMMENTS = (
    (
        "supervisor",
        "QA:這張票已排入 Sprint 2026-08A,但還沒有任何驗收契約,DoR 未通過。"
        "出貨閘門會把它列為 blocker,不是漏看,是刻意讓它擋著。",
    ),
    (
        "export",
        "PM:匯出欄位規格上期沒定案,這是順延的原因。已加上「需 UX 確認」標籤,"
        "設計確認前不要開始實作。",
    ),
    (
        "writeback",
        "RD:金流測試環境目前回 503,回寫路徑驗不了。已開缺陷追蹤,不是實作問題。",
    ),
)


def create_comments(workspace, project, owner, items):
    """Where the human gates actually get recorded.

    The Definition-of-Ready conversation, the reason a story rolled over, the note that a
    failure is environmental rather than a defect in the code -- none of these is derivable
    from the item's fields, and all of them are what someone reads first when picking the
    work up.
    """
    for issue_key, comment in COMMENTS:
        IssueComment.objects.create(
            workspace=workspace,
            project=project,
            issue=items[issue_key],
            comment_html=f"<p>{comment}</p>",
            comment_stripped=comment,
            actor=owner,
            created_by=owner,
        )
