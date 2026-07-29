# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Create a complete AI software-delivery demo project.

The command deliberately creates connected product, delivery, and QA data instead
of isolated sample rows. The resulting project can be used to demonstrate planning,
work-item extensions, traceability, execution evidence, automation, and release
gates from one coherent scenario.
"""

import base64
import datetime
from io import BytesIO
from typing import Any
from uuid import uuid4

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from plane.db.models import (
    Cycle,
    CycleIssue,
    FileAsset,
    Initiative,
    InitiativeProject,
    Issue,
    IssueAssignee,
    IssueComment,
    IssueLabel,
    IssueLink,
    IssueRelation,
    IssueType,
    Label,
    Milestone,
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
from plane.settings.storage import S3Storage
from plane.testing import ingest_automation_results
from plane.testing.services import (
    close_test_run,
    create_defect_from_result,
    create_fixed_test_run,
    create_test_case,
    create_test_folder,
    link_test_case_to_work_item,
    publish_test_case_version,
    record_test_result,
)


PREVIOUS_BUILD = "2026.07.20+4fa1c2d"
CURRENT_BUILD = "2026.07.29+5be131f"


def _step(action: str, expected: str, **metadata: Any) -> dict[str, dict[str, Any]]:
    expected_result = {"text": expected}
    expected_result.update(metadata)
    return {"action": {"text": action}, "expected_result": expected_result}


class Command(BaseCommand):
    help = (
        "Seed an end-to-end AI software-delivery demo with planning, JIRA-style work items, "
        "all custom-field kinds, labels, QA traceability, rich evidence, automation, defects, "
        "and release gates."
    )

    def add_arguments(self, parser):
        parser.add_argument("--workspace", required=True, help="Workspace slug to seed into")
        parser.add_argument("--identifier", default="AIDEMO", help="Project identifier (default: AIDEMO)")
        parser.add_argument("--owner", default=None, help="Seeding user email; defaults to workspace owner")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete and replace an existing project with the same identifier",
        )
        parser.add_argument(
            "--skip-attachments",
            action="store_true",
            help="Do not upload the two demo evidence attachments to object storage",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        workspace = self._workspace(options["workspace"])
        owner = self._owner(workspace, options["owner"])
        identifier = options["identifier"].upper()
        self._replace_existing_project(workspace, identifier, options["force"])

        project = self._create_project(workspace, owner, identifier)
        states = {state.group: state for state in State.objects.filter(project=project)}
        types = self._create_work_item_types(workspace, project)
        properties = self._create_properties(project)
        labels = self._create_labels(project, owner)
        initiative, milestones, modules, cycles = self._create_planning(project, owner)
        items = self._create_work_items(
            project,
            owner,
            states,
            types,
            properties,
            labels,
            milestones,
            modules,
            cycles,
        )
        self._create_work_item_context(project, owner, items)
        cases = self._create_test_library(project, items)
        runs = self._execute(project, owner, cases, cycles, modules)
        defect = self._close_defect_loop(project, owner, runs, states, types, labels, properties)
        self._create_release_evidence(project, owner)

        attachment_count = 0
        if not options["skip_attachments"]:
            attachment_count = self._create_attachments(project, owner, cases, runs)

        self._report(
            workspace,
            project,
            initiative,
            items,
            cases,
            runs,
            defect,
            attachment_count,
        )

    def _workspace(self, slug):
        try:
            return Workspace.objects.get(slug=slug)
        except Workspace.DoesNotExist as exc:
            raise CommandError(f"Workspace '{slug}' does not exist.") from exc

    def _owner(self, workspace, email):
        if email:
            try:
                return User.objects.get(email=email)
            except User.DoesNotExist as exc:
                raise CommandError(f"User '{email}' does not exist.") from exc
        if workspace.owner is None:
            raise CommandError("The workspace has no owner; pass --owner explicitly.")
        return workspace.owner

    def _replace_existing_project(self, workspace, identifier, force):
        existing = Project.objects.filter(workspace=workspace, identifier=identifier)
        if not existing.exists():
            return
        if not force:
            raise CommandError(
                f"Project '{identifier}' already exists in '{workspace.slug}'. "
                "Use --force to replace all of its demo data."
            )
        existing.delete()
        self.stdout.write(self.style.WARNING(f"Replaced the existing '{identifier}' project."))

    def _create_project(self, workspace, owner, identifier):
        project = Project.objects.create(
            workspace=workspace,
            name="AI DevFlow Copilot Demo",
            identifier=identifier,
            description=(
                "AI-native software delivery platform demo: product discovery, repository-aware "
                "copilot, agent automation, issue management, and QA evidence in one traceable project."
            ),
            project_lead=owner,
            created_by=owner,
        )
        State.objects.bulk_create(
            [
                State(
                    name=definition["name"],
                    color=definition["color"],
                    project=project,
                    sequence=definition["sequence"],
                    workspace=workspace,
                    group=definition["group"],
                    default=definition.get("default", False),
                    created_by=owner,
                )
                for definition in DEFAULT_STATES
            ]
        )
        workspace_role = (
            project.workspace.workspace_member.filter(member=owner, is_active=True)
            .values_list("role", flat=True)
            .first()
            or 20
        )
        ProjectMember.objects.create(
            project=project,
            member=owner,
            role=workspace_role,
            is_active=True,
            workspace=workspace,
            created_by=owner,
        )
        return project

    def _create_work_item_types(self, workspace, project):
        definitions = (
            ("Epic", "Strategic product outcome spanning multiple capabilities.", 0, True),
            ("Feature", "Cohesive user or platform capability.", 1, False),
            ("Story", "Testable user value delivered in an iteration.", 2, False),
            ("Task", "Implementation or operational work beneath a story.", 3, False),
            ("Bug", "Product defect managed through the normal delivery workflow.", 2, False),
        )
        types = {}
        for name, description, level, is_epic in definitions:
            issue_type, _created = IssueType.objects.get_or_create(
                workspace=workspace,
                name=name,
                defaults={"description": description, "is_epic": is_epic, "level": level},
            )
            ProjectIssueType.objects.create(
                project=project,
                workspace=workspace,
                issue_type=issue_type,
                level=level,
                is_default=name == "Story",
            )
            types[name] = issue_type
        return types

    def _create_properties(self, project):
        definitions = (
            (
                "Requirement kind",
                WorkItemProperty.Kind.SELECT,
                "Functional requirements define behavior; NFRs define measurable quality.",
                (("Functional", "functional"), ("Non-functional", "non_functional")),
            ),
            (
                "AI capabilities",
                WorkItemProperty.Kind.MULTI_SELECT,
                "AI building blocks exercised by the work item.",
                (
                    ("LLM", "llm"),
                    ("RAG", "rag"),
                    ("Agents", "agents"),
                    ("Evaluation", "evaluation"),
                    ("Guardrails", "guardrails"),
                ),
            ),
            (
                "Delivery note",
                WorkItemProperty.Kind.TEXT,
                "Human-readable scope or acceptance note.",
                (),
            ),
            ("Story points", WorkItemProperty.Kind.NUMBER, "Relative delivery effort.", ()),
            ("Target release", WorkItemProperty.Kind.DATE, "Planned release date.", ()),
            ("AI assisted", WorkItemProperty.Kind.BOOLEAN, "Whether AI participates in the workflow.", ()),
            (
                "Risk level",
                WorkItemProperty.Kind.SELECT,
                "Delivery, security, or model risk.",
                (("Low", "low"), ("Medium", "medium"), ("High", "high"), ("Critical", "critical")),
            ),
            ("Specification URL", WorkItemProperty.Kind.URL, "Canonical product or technical specification.", ()),
        )
        properties = {}
        for sort_order, (name, kind, description, options) in enumerate(definitions, start=1):
            prop = WorkItemProperty.objects.create(
                workspace=project.workspace,
                project=project,
                name=name,
                kind=kind,
                description=description,
                sort_order=sort_order * 1000,
                created_by=project.created_by,
            )
            for option_order, (label, value) in enumerate(options, start=1):
                WorkItemPropertyOption.objects.create(
                    workspace=project.workspace,
                    project=project,
                    property=prop,
                    label=label,
                    value=value,
                    sort_order=option_order * 1000,
                    created_by=project.created_by,
                )
            properties[name] = prop
        return properties

    def _create_labels(self, project, owner):
        definitions = (
            ("area:product", "#7C3AED", "Product discovery and workflow"),
            ("area:frontend", "#2563EB", "Web application and interaction design"),
            ("area:backend", "#0891B2", "API, persistence, and services"),
            ("area:ai", "#9333EA", "Models, prompts, RAG, and evaluation"),
            ("area:platform", "#475569", "CLI, MCP, CI, and infrastructure"),
            ("role:pm", "#F59E0B", "Product-management owned"),
            ("role:qa", "#16A34A", "Quality-engineering owned"),
            ("quality:security", "#DC2626", "Security requirement or test"),
            ("quality:privacy", "#BE123C", "Privacy and data-handling requirement"),
            ("quality:performance", "#EA580C", "Latency or throughput requirement"),
            ("quality:accessibility", "#0D9488", "Accessibility requirement"),
            ("automation", "#4F46E5", "Automated validation or workflow"),
            ("manual", "#64748B", "Manual validation or decision"),
            ("release-blocker", "#B91C1C", "Blocks the current release gate"),
        )
        return {
            name: Label.objects.create(
                workspace=project.workspace,
                project=project,
                name=name,
                color=color,
                description=description,
                created_by=owner,
            )
            for name, color, description in definitions
        }

    def _create_planning(self, project, owner):
        today = timezone.now().date()

        initiative, _created = Initiative.objects.get_or_create(
            workspace=project.workspace,
            name="AI-native software delivery foundation",
            defaults={
                "description": "Reduce lead time while keeping every AI-assisted change reviewable and testable.",
                "status": Initiative.Status.IN_PROGRESS,
                "target_date": today + datetime.timedelta(days=90),
                "created_by": owner,
            },
        )
        InitiativeProject.objects.create(
            workspace=project.workspace,
            initiative=initiative,
            project=project,
            created_by=owner,
        )
        milestones = {
            "alpha": Milestone.objects.create(
                workspace=project.workspace,
                project=project,
                name="Internal Alpha",
                description="Core planning, RAG, and QA traceability available to the internal team.",
                target_date=today - datetime.timedelta(days=7),
                status=Milestone.Status.COMPLETED,
                created_by=owner,
            ),
            "beta": Milestone.objects.create(
                workspace=project.workspace,
                project=project,
                name="Public Beta",
                description="Role-safe agent automation and evidence-rich release flow.",
                target_date=today + datetime.timedelta(days=28),
                status=Milestone.Status.IN_PROGRESS,
                created_by=owner,
            ),
        }
        modules = {
            name: Module.objects.create(
                workspace=project.workspace,
                project=project,
                name=name,
                lead=owner,
                created_by=owner,
            )
            for name in ("Product & Work Items", "RAG Copilot", "Agent Automation", "Quality & Governance")
        }

        def aware(day):
            return timezone.make_aware(datetime.datetime.combine(day, datetime.time.min))

        cycles = {
            "previous": Cycle.objects.create(
                workspace=project.workspace,
                project=project,
                name="Sprint 0 · Foundation",
                start_date=aware(today - datetime.timedelta(days=21)),
                end_date=aware(today - datetime.timedelta(days=8)),
                owned_by=owner,
                created_by=owner,
            ),
            "current": Cycle.objects.create(
                workspace=project.workspace,
                project=project,
                name="Sprint 1 · Evidence",
                start_date=aware(today - datetime.timedelta(days=7)),
                end_date=aware(today + datetime.timedelta(days=6)),
                owned_by=owner,
                created_by=owner,
            ),
            "next": Cycle.objects.create(
                workspace=project.workspace,
                project=project,
                name="Sprint 2 · Enterprise",
                start_date=aware(today + datetime.timedelta(days=7)),
                end_date=aware(today + datetime.timedelta(days=20)),
                owned_by=owner,
                created_by=owner,
            ),
        }
        return initiative, milestones, modules, cycles

    def _create_work_items(
        self,
        project,
        owner,
        states,
        types,
        properties,
        labels,
        milestones,
        modules,
        cycles,
    ):
        release_date = (timezone.now().date() + datetime.timedelta(days=28)).isoformat()

        def item(
            key,
            name,
            description,
            item_type,
            state,
            requirement_kind,
            *,
            parent=None,
            module=None,
            cycle=None,
            milestone="beta",
            priority="medium",
            label_names=(),
            capabilities=(),
            points=3,
            risk="medium",
            ai_assisted=True,
        ):
            issue = Issue.objects.create(
                workspace=project.workspace,
                project=project,
                name=name,
                description_html=f"<p>{description}</p>",
                state=states[state],
                priority=priority,
                type=types[item_type],
                parent=parent,
                milestone=milestones[milestone] if milestone else None,
                start_date=cycles[cycle].start_date.date() if cycle else None,
                target_date=cycles[cycle].end_date.date() if cycle else None,
                created_by=owner,
            )
            values = {
                "Requirement kind": requirement_kind,
                "AI capabilities": list(capabilities),
                "Delivery note": f"Demo scope: {description}",
                "Story points": points,
                "Target release": release_date,
                "AI assisted": ai_assisted,
                "Risk level": risk,
                "Specification URL": f"https://docs.example.test/ai-devflow/{key}",
            }
            for property_name, value in values.items():
                WorkItemPropertyValue.objects.create(
                    workspace=project.workspace,
                    project=project,
                    issue=issue,
                    property=properties[property_name],
                    value=value,
                    created_by=owner,
                )
            IssueAssignee.objects.create(
                workspace=project.workspace,
                project=project,
                issue=issue,
                assignee=owner,
                created_by=owner,
            )
            for label_name in label_names:
                IssueLabel.objects.create(
                    workspace=project.workspace,
                    project=project,
                    issue=issue,
                    label=labels[label_name],
                    created_by=owner,
                )
            if cycle:
                CycleIssue.objects.create(
                    workspace=project.workspace,
                    project=project,
                    cycle=cycles[cycle],
                    issue=issue,
                    created_by=owner,
                )
            if module:
                ModuleIssue.objects.create(
                    workspace=project.workspace,
                    project=project,
                    module=modules[module],
                    issue=issue,
                    created_by=owner,
                )
            return issue

        product = item(
            "epic-product",
            "AI-native product delivery workspace",
            "PM, developers, QA, and agents collaborate on one traceable delivery graph.",
            "Epic",
            "started",
            "functional",
            module="Product & Work Items",
            priority="high",
            label_names=("area:product", "role:pm"),
            capabilities=("agents",),
            points=21,
        )
        trust = item(
            "epic-trust",
            "Enterprise AI trust and release quality",
            "AI output stays scoped, attributable, measurable, and releasable.",
            "Epic",
            "started",
            "non_functional",
            module="Quality & Governance",
            priority="urgent",
            label_names=("area:ai", "role:qa", "quality:security"),
            capabilities=("evaluation", "guardrails"),
            points=21,
            risk="critical",
        )
        planning = item(
            "feature-planning",
            "JIRA-style planning and work-item search",
            "Manage typed work items, fields, labels, relationships, search, and export.",
            "Feature",
            "started",
            "functional",
            parent=product,
            module="Product & Work Items",
            priority="high",
            label_names=("area:product", "area:frontend", "area:backend"),
            points=13,
        )
        rag = item(
            "feature-rag",
            "Repository-aware AI copilot",
            "Answer and propose code changes using current repository context with citations.",
            "Feature",
            "started",
            "functional",
            parent=product,
            module="RAG Copilot",
            priority="high",
            label_names=("area:ai", "area:backend"),
            capabilities=("llm", "rag"),
            points=13,
            risk="high",
        )
        agents = item(
            "feature-agents",
            "CLI and MCP bidirectional agents",
            "Agents can inspect and update project and QA state without bypassing permissions.",
            "Feature",
            "started",
            "functional",
            parent=product,
            module="Agent Automation",
            priority="high",
            label_names=("area:platform", "automation"),
            capabilities=("agents",),
            points=13,
            risk="high",
        )
        quality = item(
            "feature-quality",
            "QA evidence and release governance",
            "Acceptance contracts, attachments, runs, defects, and release evidence form one audit trail.",
            "Feature",
            "started",
            "non_functional",
            parent=trust,
            module="Quality & Governance",
            priority="urgent",
            label_names=("role:qa", "quality:security", "release-blocker"),
            capabilities=("evaluation", "guardrails"),
            points=13,
            risk="critical",
        )

        items = {
            "epic_product": product,
            "epic_trust": trust,
            "feature_planning": planning,
            "feature_rag": rag,
            "feature_agents": agents,
            "feature_quality": quality,
        }
        story_specs = (
            (
                "issue_management",
                "PM 建立含型別、標籤與自訂欄位的工作項目",
                "建卡後可在詳情直接查看與修改所有交付欄位。",
                planning,
                "completed",
                "previous",
                "Product & Work Items",
                "functional",
                ("area:product", "role:pm"),
                (),
                5,
                "medium",
            ),
            (
                "search_export",
                "跨 Work Items 與 Test Cases 搜尋並匯出",
                "以受控查詢語法搜尋，並匯出 CSV、HTML、Excel。",
                planning,
                "completed",
                "previous",
                "Product & Work Items",
                "functional",
                ("area:frontend", "area:backend", "automation"),
                (),
                8,
                "medium",
            ),
            (
                "rag_citations",
                "Copilot 回答必須引用正確程式碼來源",
                "每個技術結論能追溯至目前 branch 的檔案與行號。",
                rag,
                "started",
                "current",
                "RAG Copilot",
                "functional",
                ("area:ai", "area:backend", "automation"),
                ("llm", "rag"),
                8,
                "high",
            ),
            (
                "agent_sync",
                "Agent 透過 CLI／MCP 雙向同步專案與 QA 狀態",
                "讀取 context 後可更新 issue、case、run 與結果，並保留追溯。",
                agents,
                "started",
                "current",
                "Agent Automation",
                "functional",
                ("area:platform", "automation"),
                ("agents",),
                8,
                "high",
            ),
            (
                "rich_evidence",
                "QA 實測結果支援 Markdown、貼圖與檔案附件",
                "Actual result 可寫 Markdown，並可貼上圖片或上傳附件供缺陷重現。",
                quality,
                "completed",
                "current",
                "Quality & Governance",
                "functional",
                ("role:qa", "area:frontend", "area:backend", "manual"),
                (),
                5,
                "medium",
            ),
            (
                "scope_masking",
                "技師／vendor 僅見自己 scope 且成本欄位遮蔽",
                "角色與資料範圍同時套用，未授權成本不出現在 API 或 UI。",
                quality,
                "started",
                "current",
                "Quality & Governance",
                "non_functional",
                ("quality:security", "quality:privacy", "release-blocker"),
                ("guardrails",),
                8,
                "critical",
            ),
            (
                "prompt_injection",
                "儲存庫內容中的 prompt injection 不得改寫 agent 指令",
                "將 repo、issue、測試文字視為不可信輸入並拒絕資料外洩。",
                quality,
                "unstarted",
                "current",
                "Quality & Governance",
                "non_functional",
                ("quality:security", "area:ai", "release-blocker"),
                ("llm", "guardrails", "evaluation"),
                8,
                "critical",
            ),
            (
                "latency",
                "Copilot 首字回應 P95 低於 3 秒",
                "在標準 repo corpus 與 50 併發使用者下維持可互動延遲。",
                rag,
                "started",
                "current",
                "RAG Copilot",
                "non_functional",
                ("quality:performance", "area:ai", "automation"),
                ("llm", "rag", "evaluation"),
                5,
                "high",
            ),
            (
                "accessibility",
                "AI 工作區符合 WCAG 2.2 AA 鍵盤操作",
                "搜尋、issue 與 testing 操作不依賴滑鼠。",
                quality,
                "backlog",
                "next",
                "Quality & Governance",
                "non_functional",
                ("quality:accessibility", "area:frontend"),
                (),
                5,
                "medium",
            ),
            (
                "dor_gap",
                "產生跨專案管理摘要",
                "已排入 sprint 但尚未建立驗收契約，用來示範 Definition of Ready 阻擋。",
                planning,
                "unstarted",
                "current",
                "Product & Work Items",
                "functional",
                ("role:pm", "release-blocker"),
                ("llm",),
                3,
                "high",
            ),
        )
        for (
            key,
            name,
            description,
            parent,
            state,
            cycle,
            module,
            kind,
            label_names,
            capabilities,
            points,
            risk,
        ) in story_specs:
            items[key] = item(
                key,
                name,
                description,
                "Story",
                state,
                kind,
                parent=parent,
                module=module,
                cycle=cycle,
                priority="urgent" if risk == "critical" else "high" if risk == "high" else "medium",
                label_names=label_names,
                capabilities=capabilities,
                points=points,
                risk=risk,
            )

        task_specs = (
            ("task_vector", "建立 repository chunk 與向量索引 pipeline", items["rag_citations"], "area:backend"),
            ("task_citation", "在回答中呈現可點擊檔案與行號引用", items["rag_citations"], "area:frontend"),
            ("task_mcp", "擴充 MCP project context 與 QA tools", items["agent_sync"], "area:platform"),
            ("task_markdown", "完成 QA Markdown evidence composer", items["rich_evidence"], "area:frontend"),
            ("task_upload", "完成 result attachment presign 與重試", items["rich_evidence"], "area:backend"),
            ("task_playwright", "建立角色遮蔽 Playwright 規格", items["scope_masking"], "role:qa"),
        )
        for key, name, parent, label_name in task_specs:
            items[key] = item(
                key,
                name,
                "可執行且可驗證的交付工作。",
                "Task",
                "completed" if parent == items["rich_evidence"] else "started",
                "functional",
                parent=parent,
                module=next(
                    module_name
                    for module_name, module in modules.items()
                    if ModuleIssue.objects.filter(module=module, issue=parent).exists()
                ),
                cycle="current",
                priority=parent.priority,
                label_names=(label_name,),
                capabilities=("agents",) if key == "task_mcp" else (),
                points=2,
                risk="medium",
            )

        items["known_bug"] = item(
            "known-bug",
            "RAG 回答在重試後偶發重複引用來源",
            "串流重試會保留第一次已輸出的 citation token。",
            "Bug",
            "started",
            "functional",
            parent=items["rag_citations"],
            module="RAG Copilot",
            cycle="current",
            priority="high",
            label_names=("area:ai", "area:backend", "release-blocker"),
            capabilities=("llm", "rag"),
            points=3,
            risk="high",
        )
        return items

    def _create_work_item_context(self, project, owner, items):
        IssueRelation.objects.create(
            workspace=project.workspace,
            project=project,
            issue=items["rag_citations"],
            related_issue=items["known_bug"],
            relation_type="blocked_by",
            created_by=owner,
        )
        IssueRelation.objects.create(
            workspace=project.workspace,
            project=project,
            issue=items["rich_evidence"],
            related_issue=items["task_markdown"],
            relation_type="implemented_by",
            created_by=owner,
        )
        IssueLink.objects.create(
            workspace=project.workspace,
            project=project,
            issue=items["agent_sync"],
            title="MCP integration design",
            url="https://docs.example.test/ai-devflow/mcp-integration",
            metadata={"kind": "design"},
            created_by=owner,
        )
        IssueComment.objects.create(
            workspace=project.workspace,
            project=project,
            issue=items["scope_masking"],
            actor=owner,
            comment_html=(
                "<p><strong>Release decision:</strong> vendor scope and cost masking must pass before Public Beta.</p>"
            ),
            created_by=owner,
        )

    def _create_test_library(self, project, items):
        root = create_test_folder(project_id=project.id, name="AI DevFlow Copilot", sort_order=1000)
        folders = {
            "planning": create_test_folder(
                project_id=project.id, name="Product & Work Items", parent_id=root.id, sort_order=1000
            ),
            "rag": create_test_folder(project_id=project.id, name="RAG Copilot", parent_id=root.id, sort_order=2000),
            "agents": create_test_folder(
                project_id=project.id, name="Agent Automation", parent_id=root.id, sort_order=3000
            ),
            "evidence": create_test_folder(
                project_id=project.id, name="QA Evidence & Export", parent_id=root.id, sort_order=4000
            ),
            "security": create_test_folder(
                project_id=project.id, name="Security & Privacy", parent_id=root.id, sort_order=5000
            ),
            "quality": create_test_folder(
                project_id=project.id, name="Performance & Accessibility", parent_id=root.id, sort_order=6000
            ),
        }

        def case(key, title, folder, steps, *, priority="high", case_type="functional", tags=(), preconditions=None):
            return create_test_case(
                project_id=project.id,
                title=title,
                folder_id=folders[folder].id,
                description={"text": f"Acceptance contract for {title}", "format": "markdown"},
                preconditions=preconditions or {},
                priority=priority,
                case_type=case_type,
                tags=list(tags),
                steps=steps,
            )

        cases = {
            "issue_fields": case(
                "issue_fields",
                "建立工作項目可保存型別、標籤與七種欄位",
                "planning",
                [_step("建立 Story 並填入所有自訂欄位", "詳情與 API 回傳相同型別和值")],
                tags=("manual", "smoke", "work-items"),
            ),
            "search_export": case(
                "search_export",
                "跨 Work Items 與 Test Cases 搜尋並匯出 CSV／HTML／Excel",
                "planning",
                [
                    _step("搜尋 type:test_case priority:high AI", "只回傳符合條件的案例"),
                    _step("切換 scope=all 並匯出三種格式", "三種檔案皆含目前查詢結果"),
                ],
                tags=("automated", "search", "export"),
            ),
            "rag_citation": case(
                "rag_citation",
                "Copilot 技術回答引用目前 branch 的檔案與行號",
                "rag",
                [
                    _step("詢問測試結果如何寫入", "回答引用實際 service 與 API 路由"),
                    _step("開啟每個 citation", "檔案存在且行號內容支持該結論"),
                ],
                tags=("automated", "rag", "smoke"),
                preconditions={"text": "索引已同步至 build 5be131f"},
            ),
            "rag_retry": case(
                "rag_retry",
                "串流重試不會重複輸出 citation",
                "rag",
                [_step("在 citation token 後中斷並重試串流", "每個來源只顯示一次")],
                tags=("automated", "negative", "rag"),
            ),
            "agent_sync": case(
                "agent_sync",
                "Agent 經 CLI／MCP 讀取 context 後雙向更新",
                "agents",
                [
                    _step("呼叫 project_get_context", "取得專案、state 與 testing capabilities"),
                    _step("建立 issue、連結 case 並記錄結果", "所有資料留在同一專案且可雙向查回"),
                ],
                tags=("automated", "mcp", "cli"),
            ),
            "rich_evidence": case(
                "rich_evidence",
                "Actual result 支援 Markdown、貼圖與檔案附件",
                "evidence",
                [
                    _step("在 Actual result 貼上 Markdown 清單與程式碼", "預覽保留格式且安全呈現"),
                    _step("直接貼上圖片並選擇 log 檔", "兩個檔案可重試上傳並掛在同一 result"),
                    _step("由失敗結果建立 defect", "缺陷含 Markdown 觀察、執行環境與可追溯連結"),
                ],
                tags=("manual", "attachment", "markdown", "smoke"),
            ),
            "scope_masking": case(
                "scope_masking",
                "技師／vendor 僅見自己 scope 且成本欄位遮蔽",
                "security",
                [
                    _step("以 vendor A 查詢佣金 statement", "只回傳 vendor A 自己的 statement"),
                    _step("檢查 API 與畫面 payload", "未授權角色看不到成本欄位與其他 vendor 資料"),
                ],
                priority="urgent",
                case_type="security",
                tags=("manual", "security", "privacy", "negative", "release-blocker"),
                preconditions={"text": "vendor A、vendor B 各有 statement；成本欄位僅 Finance 可讀"},
            ),
            "prompt_injection": case(
                "prompt_injection",
                "Repo 與 issue 中的 prompt injection 不得外洩系統資訊",
                "security",
                [_step("索引含惡意 instruction 的文件後詢問 Agent", "Agent 視其為資料並拒絕洩漏密鑰或改寫規則")],
                priority="urgent",
                case_type="security",
                tags=("automated", "security", "ai-safety", "negative", "release-blocker"),
            ),
            "latency": case(
                "latency",
                "Copilot 首字回應 P95 低於 3 秒",
                "quality",
                [
                    _step(
                        "以 50 VU 執行標準 repo 問答",
                        "P95 首字延遲 < 3,000 ms",
                        metric="ttft_p95",
                        operator="<",
                        threshold=3000,
                        unit="ms",
                    )
                ],
                case_type="performance",
                tags=("automated", "performance", "threshold"),
            ),
            "accessibility": case(
                "accessibility",
                "搜尋、issue 與 testing 流程可完全鍵盤操作",
                "quality",
                [_step("只使用鍵盤完成搜尋、開卡與記錄結果", "焦點可見、順序合理且無 keyboard trap")],
                case_type="compliance",
                tags=("manual", "accessibility", "wcag"),
            ),
            "reliability": case(
                "reliability",
                "Agent 更新 API 24 小時成功率至少 99.9%",
                "quality",
                [
                    _step(
                        "統計 24 小時 MCP／CLI 寫入",
                        "成功率 >= 99.9%",
                        metric="agent_write_success",
                        operator=">=",
                        threshold=99.9,
                        unit="%",
                    )
                ],
                case_type="reliability",
                tags=("automated", "reliability", "threshold"),
            ),
        }
        links = (
            ("issue_fields", "issue_management"),
            ("search_export", "search_export"),
            ("rag_citation", "rag_citations"),
            ("rag_retry", "rag_citations"),
            ("agent_sync", "agent_sync"),
            ("rich_evidence", "rich_evidence"),
            ("scope_masking", "scope_masking"),
            ("prompt_injection", "prompt_injection"),
            ("latency", "latency"),
            ("accessibility", "accessibility"),
            ("reliability", "agent_sync"),
        )
        for case_key, item_key in links:
            link_test_case_to_work_item(
                test_case_id=cases[case_key].id,
                issue_id=items[item_key].id,
                project_id=project.id,
            )
        return cases

    def _execute(self, project, owner, cases, cycles, modules):
        previous_keys = ("issue_fields", "search_export", "rag_citation")
        previous = create_fixed_test_run(
            project_id=project.id,
            name="Sprint 0 · Foundation acceptance",
            test_case_ids=[cases[key].id for key in previous_keys],
            build=PREVIOUS_BUILD,
            configuration={"browser": "Chromium 128", "environment": "staging"},
            cycle_id=cycles["previous"].id,
            module_id=modules["Product & Work Items"].id,
            description={"text": "Foundation acceptance and baseline evidence."},
        )
        previous_cases = {run_case.test_case_id: run_case for run_case in previous.run_cases.all()}
        for key, observation, duration in (
            ("issue_fields", "所有欄位與標籤在 UI／API 一致。", 44000),
            ("search_export", "CSV、HTML、XLSX 各 12 筆且 UTF-8 正確。", 18000),
            ("rag_citation", "5 個 citation 全數可開啟且支持回答。", 6200),
        ):
            record_test_result(
                run_case_id=previous_cases[cases[key].id].id,
                project_id=project.id,
                status="passed",
                executed_by=owner,
                actual_result={"text": observation, "format": "markdown"},
                duration_ms=duration,
            )
        close_test_run(test_run_id=previous.id, project_id=project.id)

        publish_test_case_version(
            test_case_id=cases["rich_evidence"].id,
            project_id=project.id,
            title="Actual result 支援 Markdown、貼圖、檔案附件與失敗重試",
            description={"text": "Result evidence remains append-only; attachment retries never duplicate the result."},
            preconditions={"text": "允許 image/png、text/plain，單檔不超過 instance limit"},
            priority="high",
            case_type="functional",
            tags=["manual", "attachment", "markdown", "retry", "smoke"],
            steps=[
                _step("輸入 Markdown 並貼上圖片與 console.log", "畫面保留草稿並顯示兩個待上傳檔案"),
                _step("記錄 failed result，模擬 log 第一次上傳失敗", "result 只建立一次，失敗檔案可單獨重試"),
                _step("重試附件並建立 defect", "缺陷含原始 Markdown、環境、步驟與 result 追溯"),
            ],
        )

        ingestion, _replayed = ingest_automation_results(
            project_id=project.id,
            idempotency_key="ai-demo:playwright:2026-07-29:1",
            source="playwright",
            name="main / Playwright regression #128",
            build=CURRENT_BUILD,
            configuration={"browser": "chromium", "environment": "staging"},
            created_by=owner,
            results=[
                {
                    "external_id": "planning/search-export",
                    "title": "Search and export",
                    "test_case_id": str(cases["search_export"].id),
                    "status": "passed",
                    "duration_ms": 9100,
                    "actual_result": {"text": "3 export formats verified", "format": "markdown"},
                },
                {
                    "external_id": "rag/citations",
                    "title": "RAG citations",
                    "test_case_id": str(cases["rag_citation"].id),
                    "status": "passed",
                    "duration_ms": 4100,
                    "actual_result": {"text": "All citations resolved"},
                },
                {
                    "external_id": "agent/mcp-sync",
                    "title": "MCP bidirectional sync",
                    "test_case_id": str(cases["agent_sync"].id),
                    "status": "passed",
                    "duration_ms": 2300,
                    "actual_result": {"text": "Context, issue, case, and result round-trip passed"},
                },
            ],
        )
        close_test_run(test_run_id=ingestion.test_run_id, project_id=project.id)

        current_keys = (
            "rag_retry",
            "agent_sync",
            "rich_evidence",
            "scope_masking",
            "prompt_injection",
            "latency",
            "reliability",
        )
        current = create_fixed_test_run(
            project_id=project.id,
            name="Sprint 1 · Evidence release candidate",
            test_case_ids=[cases[key].id for key in current_keys],
            build=CURRENT_BUILD,
            configuration={
                "browser": "Chromium 128",
                "environment": "staging",
                "model": "demo-copilot-2026-07",
                "region": "ap-northeast-1",
            },
            cycle_id=cycles["current"].id,
            module_id=modules["Quality & Governance"].id,
            description={"text": "Release candidate with manual evidence and enterprise guardrails."},
        )
        current_cases = {run_case.test_case_id: run_case for run_case in current.run_cases.all()}

        pass_results = {}
        for key, observation, duration in (
            ("agent_sync", "CLI／MCP round-trip 通過，所有 link 均保持同專案。", 4700),
            (
                "rich_evidence",
                "## 驗證結果\n\n- Markdown 預覽正確\n- 圖片可貼上\n- 失敗附件可重試\n\n`result_id` 未重複建立。",
                72000,
            ),
            ("scope_masking", "vendor A 僅見自己的 statement；API payload 不含 cost。", 55000),
            ("latency", "P95 TTFT = 2,840 ms，低於 3,000 ms 門檻。", 300000),
        ):
            pass_results[key] = record_test_result(
                run_case_id=current_cases[cases[key].id].id,
                project_id=project.id,
                status="passed",
                executed_by=owner,
                actual_result={"text": observation, "format": "markdown"},
                duration_ms=duration,
            )
        reliability = record_test_result(
            run_case_id=current_cases[cases["reliability"].id].id,
            project_id=project.id,
            status="failed",
            executed_by=owner,
            actual_result={
                "text": "24h 成功率 **99.72%**，低於 99.9% 門檻。",
                "format": "markdown",
                "measured": 99.72,
                "unit": "%",
                "metric": "agent_write_success",
                "artifacts": ["https://grafana.example.test/d/agent-write-slo"],
            },
            duration_ms=86400000,
        )
        prompt = record_test_result(
            run_case_id=current_cases[cases["prompt_injection"].id].id,
            project_id=project.id,
            status="blocked",
            executed_by=owner,
            actual_result={
                "text": "等待安全團隊核准 red-team corpus，尚不能宣告通過。",
                "format": "markdown",
            },
            duration_ms=9000,
        )
        retry_failure = record_test_result(
            run_case_id=current_cases[cases["rag_retry"].id].id,
            project_id=project.id,
            status="failed",
            executed_by=owner,
            actual_result={
                "text": "中斷於第 2 個 citation 後重試，來源 `services.py:165` 顯示兩次。",
                "format": "markdown",
                "artifacts": ["https://logs.example.test/traces/rag-retry-128"],
            },
            duration_ms=12400,
        )
        return {
            "previous": previous,
            "automation": ingestion.test_run,
            "current": current,
            "current_cases": current_cases,
            "pass_results": pass_results,
            "reliability_failure": reliability,
            "prompt_blocked": prompt,
            "retry_failure": retry_failure,
        }

    def _close_defect_loop(self, project, owner, runs, states, types, labels, properties):
        run_case = runs["current_cases"][runs["retry_failure"].run_case.test_case_id]
        defect = create_defect_from_result(
            result_id=runs["retry_failure"].id,
            run_case_id=run_case.id,
            project_id=project.id,
            created_by=owner,
            name="RAG 串流重試會重複 citation",
            priority="high",
        ).issue
        defect.type = types["Bug"]
        defect.state = states["completed"]
        defect.save(update_fields=["type", "state", "updated_at"])
        IssueLabel.objects.create(
            workspace=project.workspace,
            project=project,
            issue=defect,
            label=labels["area:ai"],
            created_by=owner,
        )
        WorkItemPropertyValue.objects.create(
            workspace=project.workspace,
            project=project,
            issue=defect,
            property=properties["Risk level"],
            value="high",
            created_by=owner,
        )
        record_test_result(
            run_case_id=run_case.id,
            project_id=project.id,
            status="passed",
            executed_by=owner,
            actual_result={
                "text": "修正後重驗：中斷三次仍各只顯示一組 citation。",
                "format": "markdown",
            },
            duration_ms=11800,
        )
        return defect

    def _create_release_evidence(self, project, owner):
        evidence = (
            (
                "slo",
                "availability",
                "Copilot availability 30d",
                "passing",
                "99.95% ≥ 99.9%",
                "https://grafana.example.test/d/copilot-slo",
            ),
            (
                "scan",
                "dependencies",
                "Dependency and container scan",
                "passing",
                "0 critical; 0 high exploitable",
                "https://security.example.test/scans/aidemo",
            ),
            ("scan", "model-red-team", "Prompt injection red-team", "pending", "Awaiting approved corpus", ""),
            (
                "review",
                "privacy",
                "Privacy and data-retention review",
                "passing",
                "DPA and 30-day retention approved",
                "https://docs.example.test/reviews/privacy",
            ),
            ("review", "release-signoff", "Public Beta sign-off", "pending", "QA and Product approval required", ""),
        )
        for kind, key, name, status, detail, source_url in evidence:
            ReleaseEvidence.objects.create(
                workspace=project.workspace,
                project=project,
                kind=kind,
                key=key,
                name=name,
                status=status,
                detail=detail,
                source_url=source_url,
                created_by=owner,
            )

    def _create_attachments(self, project, owner, cases, runs):
        tiny_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nGQAAAAASUVORK5CYII="
        )
        attachments = (
            (
                str(cases["rich_evidence"].id),
                "rich-evidence-acceptance.md",
                "text/markdown",
                b"# Rich evidence acceptance\n\n- Markdown\n- pasted images\n- retryable files\n",
            ),
            (
                str(runs["pass_results"]["rich_evidence"].id),
                "pasted-result-screenshot.png",
                "image/png",
                tiny_png,
            ),
        )
        storage = S3Storage()
        created = 0
        for entity_identifier, name, mime_type, body in attachments:
            object_name = f"{project.workspace_id}/{uuid4().hex}-{name}"
            try:
                uploaded = storage.upload_file(BytesIO(body), object_name, content_type=mime_type)
            except Exception as exc:  # storage may intentionally be absent in a developer checkout
                self.stderr.write(self.style.WARNING(f"Skipped demo attachment '{name}': {exc}"))
                continue
            if not uploaded:
                self.stderr.write(self.style.WARNING(f"Skipped demo attachment '{name}': upload failed"))
                continue
            FileAsset.objects.create(
                workspace=project.workspace,
                project=project,
                user=owner,
                asset=object_name,
                attributes={"name": name, "type": mime_type, "size": len(body)},
                size=len(body),
                is_uploaded=True,
                entity_type=FileAsset.EntityTypeContext.TESTING_ARTIFACT,
                entity_identifier=entity_identifier,
                created_by=owner,
            )
            created += 1
        return created

    def _report(self, workspace, project, initiative, items, cases, runs, defect, attachment_count):
        base = f"/{workspace.slug}/projects/{project.id}"
        write = self.stdout.write
        write(self.style.SUCCESS(f"Seeded {project.identifier} · {project.name} ({project.id})"))
        write("")
        write(f"  Initiative       {initiative.name}")
        write("  Delivery graph   2 epics / 4 features / 10 stories / 6 tasks / 2 bugs")
        write("  Configuration    5 work-item types / 8 fields covering all 7 kinds / 14 labels")
        write(f"  QA library       {len(cases)} versioned cases in 7 folders with Story traceability")
        write("  Evidence         1 closed manual run / 1 CI ingestion / 1 active release run")
        write(f"  Defect loop      {project.identifier}-{defect.sequence_id} fixed and retested append-only")
        write(f"  Attachments      {attachment_count}/2 uploaded to object storage")
        write("  Release gate     intentionally blocked by reliability, prompt-injection, and DoR evidence")
        write("")
        write(f"  project          {base}/issues")
        write(f"  testing overview {base}/testing/overview")
        write(f"  test cases       {base}/testing/cases")
        write(f"  test runs        {base}/testing/runs")
        write("")
        write(f"  Search examples: type:test_case tag:security · priority:high AI · {project.identifier}-1")
        write(f"  Seeded {len(items)} named work-item examples and builds {PREVIOUS_BUILD}, {CURRENT_BUILD}.")
