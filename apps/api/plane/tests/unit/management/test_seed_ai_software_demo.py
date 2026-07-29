# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from io import StringIO

import pytest
from django.core.management import call_command

from plane.db.models import (
    InitiativeProject,
    Issue,
    IssueType,
    Label,
    Milestone,
    Project,
    ProjectIssueType,
    ReleaseEvidence,
    TestAutomationIngestion as AutomationIngestion,
    TestCase as Case,
    TestFolder as Folder,
    TestResultIssueLink as ResultIssueLink,
    TestRun as Run,
    WorkItemProperty,
)


@pytest.mark.unit
@pytest.mark.django_db
def test_seed_ai_software_demo_builds_connected_delivery_and_qa_graph(workspace):
    stdout = StringIO()

    call_command(
        "seed_ai_software_demo",
        workspace=workspace.slug,
        identifier="AIDEMO",
        skip_attachments=True,
        stdout=stdout,
    )

    project = Project.objects.get(workspace=workspace, identifier="AIDEMO")
    assert project.name == "AI DevFlow Copilot Demo"
    assert "5 work-item types / 8 fields" in stdout.getvalue()

    enabled_types = ProjectIssueType.objects.filter(project=project).select_related("issue_type")
    assert {row.issue_type.name for row in enabled_types} == {"Epic", "Feature", "Story", "Task", "Bug"}
    assert IssueType.objects.filter(workspace=workspace, name="Epic", is_epic=True, level=0).exists()

    properties = WorkItemProperty.objects.filter(project=project)
    assert properties.count() == 8
    assert set(properties.values_list("kind", flat=True)) == set(WorkItemProperty.Kind.values)
    assert Label.objects.filter(project=project).count() == 14
    assert Milestone.objects.filter(project=project).count() == 2
    assert InitiativeProject.objects.filter(project=project).count() == 1

    rich_evidence = Issue.objects.get(project=project, name__startswith="QA 實測結果支援")
    assert rich_evidence.property_values.count() == 8
    assert rich_evidence.label_issue.count() >= 4
    assert rich_evidence.parent.type.name == "Feature"
    assert rich_evidence.issue_cycle.count() == 1
    assert rich_evidence.issue_module.count() == 1

    assert Issue.objects.filter(project=project, type__name="Epic").count() == 2
    assert Issue.objects.filter(project=project, type__name="Feature").count() == 4
    assert Issue.objects.filter(project=project, type__name="Story").count() == 10
    assert Issue.objects.filter(project=project, type__name="Task").count() == 6
    assert Issue.objects.filter(project=project, type__name="Bug").count() == 2

    assert Folder.objects.filter(project=project).count() == 7
    assert Case.objects.filter(project=project).count() == 11
    rich_case = Case.objects.get(
        project=project,
        versions__title="Actual result 支援 Markdown、貼圖、檔案附件與失敗重試",
    )
    assert rich_case.current_version == 2
    assert rich_case.work_item_links.filter(issue=rich_evidence).exists()

    runs = Run.objects.filter(project=project)
    assert runs.count() == 3
    assert runs.filter(status="completed").count() == 2
    assert runs.filter(status="active", cycle__name="Sprint 1 · Evidence").count() == 1
    assert AutomationIngestion.objects.filter(project=project, source="playwright").count() == 1
    assert ResultIssueLink.objects.filter(project=project).count() == 1
    assert ReleaseEvidence.objects.filter(project=project).count() == 5
