# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Everything a work item can be classified by, created before any work item exists.

Five mechanisms overlap here and the demo exists partly to keep them apart:

- **type** places an item on the breakdown axis (epic, feature, story)
- **property** records a fact about the requirement itself (its kind, its plant, its
  audit obligation) and crosses the breakdown freely
- **label** is a cross-cutting tag with no schema, useful precisely because anyone can
  add one without a migration
- **estimate** sizes the work, and only ever at story level
- **milestone** is a delivery checkpoint, which is neither a sprint nor a module

Collapsing any two of these is the recurring modelling mistake. A plant is not a label,
because "which plants does this affect" has a closed set of answers and wants a typed
value; "needs legal review" is not a property, because nobody can enumerate the tags a
team will want next quarter.
"""

# Python imports
import datetime

# Django imports
from django.utils import timezone

# Module imports
from plane.db.models import (
    Estimate,
    EstimatePoint,
    IssueType,
    Label,
    Milestone,
    Project,
    ProjectIssueType,
    ProjectMember,
    State,
    WorkItemProperty,
    WorkItemPropertyOption,
)
from plane.db.models.state import DEFAULT_STATES

PROJECT_NAME = "Shop-floor Quality Platform"
PROJECT_DESCRIPTION = (
    "Production traceability and AI defect review. Three axes cross rather than nest: "
    "the work breakdown runs epic to feature to story, every requirement is classified "
    "functional or non-functional independently of where it sits, and scheduling is three "
    "separate cross-sections -- sprint, module and milestone."
)


def create_project(workspace, owner, identifier):
    """The project, with every axis it is about to be populated with made reachable.

    The three `*_view` flags are set explicitly rather than left to the model default. They
    now default on, so this is redundant today -- and that is the point. This seed creates
    two sprints, two modules and seven saved views; if a future upstream rebase flips the
    default back, the demo would go on creating all of it while the sidebar showed none of
    it, which is exactly the failure that made these lines necessary in the first place.
    Stating the intent here means the demo breaks loudly instead of quietly.
    """
    project = Project.objects.create(
        workspace=workspace,
        name=PROJECT_NAME,
        identifier=identifier,
        description=PROJECT_DESCRIPTION,
        project_lead=owner,
        created_by=owner,
        cycle_view=True,
        module_view=True,
        issue_views_view=True,
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


def create_work_item_types(workspace, project):
    """Axis one: how the work is broken down.

    Epic, feature and story only. An earlier version of this seed also created a
    "Quality requirement" type sitting beside Story, which quietly folded the
    requirement-nature axis into the breakdown axis -- exactly the collapse the product
    definition warns against. Nature is a property; see below.
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


# name -> (kind, description, [(label, value), ...])
PROPERTY_DEFINITIONS = (
    (
        "Requirement kind",
        WorkItemProperty.Kind.SELECT,
        "Functional requirements say what the system does; non-functional ones say how well.",
        (("Functional (FR)", "functional"), ("Non-functional (NFR)", "non_functional")),
    ),
    (
        "目標廠區",
        WorkItemProperty.Kind.MULTI_SELECT,
        "這條需求要在哪些廠區生效。多選,因為同一條需求常同時涵蓋數個廠區。",
        (("CN21 昆山", "CN21"), ("CN22 蘇州", "CN22"), ("VN01 河內", "VN01")),
    ),
    (
        "需法規稽核",
        WorkItemProperty.Kind.BOOLEAN,
        "為真時,這條需求的驗收紀錄必須保留供稽核調閱。",
        (),
    ),
    (
        "客戶承諾日",
        WorkItemProperty.Kind.DATE,
        "對客戶承諾的交付日期,與 sprint 的 target_date 是兩回事。",
        (),
    ),
    (
        "影響產線數",
        WorkItemProperty.Kind.NUMBER,
        "這條需求若失敗會影響幾條產線,用來排序風險。",
        (),
    ),
)


def create_properties(project):
    """Axis two and its neighbours: what kind of requirement this is.

    Requirement kind crosses the breakdown rather than nesting inside it -- an epic, a
    feature and a story can each be functional or non-functional. Keeping it a property
    is what lets a feature carry a quality constraint without inventing a parallel
    hierarchy for it.

    The other four exist to show every property kind the schema supports, and to make
    the point that a property is a typed fact about the requirement. None of them is a
    label, and none belongs in the item's title.
    """
    properties = {}
    for index, (name, kind, description, options) in enumerate(PROPERTY_DEFINITIONS):
        prop = WorkItemProperty.objects.create(
            project=project,
            workspace=project.workspace,
            name=name,
            description=description,
            kind=kind,
            sort_order=(index + 1) * 1000,
        )
        for option_index, (label, value) in enumerate(options):
            WorkItemPropertyOption.objects.create(
                property=prop,
                project=project,
                workspace=project.workspace,
                label=label,
                value=value,
                sort_order=(option_index + 1) * 1000,
            )
        properties[name] = prop
    return properties


# name -> (colour, description)
LABEL_DEFINITIONS = (
    ("法規稽核", "#DC2626", "受稽核規範約束,驗收紀錄需保留一年。"),
    ("客戶承諾", "#EA580C", "已對客戶承諾日期,延誤需對外說明。"),
    ("技術債", "#6B7280", "已知的權宜實作,排期償還。"),
    ("跨團隊相依", "#7C3AED", "需要平台組或 MES team 配合才能完成。"),
    ("需 UX 確認", "#2563EB", "介面行為未定案,實作前需設計確認。"),
    ("上期順延", "#CA8A04", "自上一個 sprint 未完成而捲動進來。"),
)


def create_labels(workspace, project, owner):
    """Cross-cutting tags with no schema.

    A label answers "what else is true about this" for questions nobody enumerated in
    advance. That openness is the point, and also why a label must not carry anything
    the system needs to reason about -- coverage, the release gate and the roll-up all
    read types, properties and states, never labels.
    """
    return {
        name: Label.objects.create(
            workspace=workspace,
            project=project,
            name=name,
            color=color,
            description=description,
            sort_order=(index + 1) * 1000,
            created_by=owner,
        )
        for index, (name, color, description) in enumerate(LABEL_DEFINITIONS)
    }


def create_estimate(project, workspace, owner):
    """Story points, and the aggregation axis they are read along.

    Only stories carry a point value, for the same reason only stories carry contracts:
    both are decided at the level where a unit of work is small enough to judge.

    Where the two part company is what happens above that level. Coverage rolls up the
    **breakdown** -- a feature reports the contracts of its descendants. Estimates do not.
    Nothing sums points to a parent; the aggregate Plane computes is per **cycle**, for
    sprint burndown. So an epic shows no total, and asking "how big is this epic" is a
    question the schema declines to answer.

    Two mechanics worth knowing before reading any burndown number:

    - `key` is a 1-based ordinal, `value` is the displayed figure. Plane's own Fibonacci
      preset pairs key 1-6 with values 1, 2, 3, 5, 8, 13, and this seed matches it
    - the burndown sums `key`, not `value`. A sprint holding 5 + 8 + 13 points reports
      4 + 5 + 6 = 15, not 26. That is upstream behaviour and is left alone here, but it
      means the figure orders sprints correctly while not being a point total
    """
    estimate = Estimate.objects.create(
        project=project,
        workspace=workspace,
        name="Fibonacci",
        description="Story points, on stories only. Aggregated per cycle for burndown, never to a parent.",
        type="points",
        last_used=True,
        created_by=owner,
    )
    points = {
        value: EstimatePoint.objects.create(
            estimate=estimate,
            project=project,
            workspace=workspace,
            key=index + 1,
            value=value,
            created_by=owner,
        )
        for index, value in enumerate(("1", "2", "3", "5", "8", "13"))
    }
    Project.objects.filter(id=project.id).update(estimate=estimate)
    return points


def create_milestones(project, workspace, owner):
    """The third scheduling cross-section, and the one most often confused with a sprint.

    A sprint is a fixed window the team works inside; a milestone is a commitment the
    delivery is measured against. They do not line up: `M2` below spans both sprints,
    and a story finishing in Sprint 2026-08A can still belong to a milestone that closes
    two months later. Modelling either as the other loses the distinction between "when
    did we work on it" and "what did we promise it for".
    """
    today = timezone.now().date()
    definitions = (
        ("M1 履歷查詢上線", "completed", -7, "工單與序號查詢對 CN21 開放。"),
        ("M2 NG 修正與回寫", "in_progress", 21, "IE 可修正誤判並回寫 MES,涵蓋兩個 sprint。"),
        ("M3 稽核報表與合規", "planned", 60, "匯出稽核報表,滿足保留一年的法規要求。"),
    )
    return {
        name: Milestone.objects.create(
            project=project,
            workspace=workspace,
            name=name,
            description=description,
            status=status,
            target_date=today + datetime.timedelta(days=offset),
            sort_order=(index + 1) * 1000,
            created_by=owner,
        )
        for index, (name, status, offset, description) in enumerate(definitions)
    }
