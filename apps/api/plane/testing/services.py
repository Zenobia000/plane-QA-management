# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.html import escape

from plane.db.models import (
    Cycle,
    Issue,
    Module,
    Project,
    TestCase,
    TestCaseVersion,
    TestCaseWorkItemLink,
    TestFolder,
    TestResult,
    TestResultIssueLink,
    TestRun,
    TestRunCase,
    TestStep,
)


def _validate_domain_model(instance):
    # Plane audit FKs are nullable at the database layer but intentionally not form fields.
    instance.full_clean(exclude=("created_by", "updated_by"))


def _folder_for_project(project, folder_id):
    if folder_id is None:
        return None
    try:
        return TestFolder.objects.get(id=folder_id, project=project)
    except TestFolder.DoesNotExist as exc:
        raise ValidationError("The test folder does not belong to this project.") from exc


def _create_steps(version, steps):
    return [
        TestStep.objects.create(
            project=version.project,
            workspace=version.workspace,
            test_case_version=version,
            position=position,
            action=step["action"],
            expected_result=step.get("expected_result", {}),
        )
        for position, step in enumerate(steps, start=1)
    ]


@transaction.atomic
def create_test_folder(*, project_id, name, parent_id=None, sort_order=65535):
    project = Project.objects.select_for_update().get(id=project_id)
    parent = _folder_for_project(project, parent_id)
    folder = TestFolder(
        project=project,
        workspace=project.workspace,
        name=name.strip(),
        parent=parent,
        sort_order=sort_order,
    )
    _validate_domain_model(folder)
    folder.save()
    return folder


@transaction.atomic
def create_test_case(
    *,
    project_id,
    title,
    folder_id=None,
    description=None,
    preconditions=None,
    priority="none",
    case_type="functional",
    tags=None,
    steps=None,
):
    project = Project.objects.select_for_update().get(id=project_id)
    folder = _folder_for_project(project, folder_id)
    last_sequence = TestCase.objects.filter(project=project).aggregate(value=Max("sequence"))["value"] or 0
    test_case = TestCase(
        project=project,
        workspace=project.workspace,
        folder=folder,
        sequence=last_sequence + 1,
        current_version=1,
    )
    _validate_domain_model(test_case)
    test_case.save()
    version = TestCaseVersion.objects.create(
        project=project,
        workspace=project.workspace,
        test_case=test_case,
        version=1,
        title=title.strip(),
        description=description or {},
        preconditions=preconditions or {},
        priority=priority,
        case_type=case_type,
        tags=tags or [],
    )
    _create_steps(version, steps or [])
    return test_case


@transaction.atomic
def publish_test_case_version(
    *,
    test_case_id,
    project_id,
    title,
    description=None,
    preconditions=None,
    priority="none",
    case_type="functional",
    tags=None,
    steps=None,
):
    test_case = TestCase.objects.select_for_update().get(id=test_case_id, project_id=project_id)
    next_version = test_case.current_version + 1
    version = TestCaseVersion.objects.create(
        project=test_case.project,
        workspace=test_case.workspace,
        test_case=test_case,
        version=next_version,
        title=title.strip(),
        description=description or {},
        preconditions=preconditions or {},
        priority=priority,
        case_type=case_type,
        tags=tags or [],
    )
    _create_steps(version, steps or [])
    TestCase.objects.filter(id=test_case.id).update(current_version=next_version)
    test_case.current_version = next_version
    return test_case


@transaction.atomic
def link_test_case_to_work_item(*, test_case_id, issue_id, project_id):
    test_case = TestCase.objects.select_for_update().get(id=test_case_id, project_id=project_id)
    issue = Issue.objects.get(id=issue_id, project_id=project_id, is_draft=False)
    link = TestCaseWorkItemLink(
        project=test_case.project,
        workspace=test_case.workspace,
        test_case=test_case,
        issue=issue,
    )
    _validate_domain_model(link)
    link.save()
    return link


@transaction.atomic
def create_fixed_test_run(
    *,
    project_id,
    name,
    test_case_ids,
    description=None,
    build="",
    configuration=None,
    cycle_id=None,
    module_id=None,
):
    project = Project.objects.select_for_update().get(id=project_id)
    unique_case_ids = list(dict.fromkeys(test_case_ids))
    cases = {
        str(item.id): item
        for item in TestCase.objects.select_for_update()
        .filter(id__in=unique_case_ids, project=project, archived_at__isnull=True)
        .prefetch_related("versions")
    }
    if len(cases) != len(unique_case_ids):
        raise ValidationError("Every selected test case must be active and belong to this project.")
    cycle = Cycle.objects.get(id=cycle_id, project=project) if cycle_id else None
    module = Module.objects.get(id=module_id, project=project) if module_id else None
    test_run = TestRun(
        project=project,
        workspace=project.workspace,
        name=name.strip(),
        description=description or {},
        status="active",
        run_type="fixed",
        build=build,
        configuration=configuration or {},
        cycle=cycle,
        module=module,
    )
    _validate_domain_model(test_run)
    test_run.save()
    for position, case_id in enumerate(unique_case_ids, start=1):
        test_case = cases[str(case_id)]
        version = next(
            item for item in test_case.versions.all() if item.version == test_case.current_version
        )
        run_case = TestRunCase(
            project=project,
            workspace=project.workspace,
            test_run=test_run,
            test_case=test_case,
            test_case_version=version,
            position=position,
        )
        _validate_domain_model(run_case)
        run_case.save()
    return test_run


@transaction.atomic
def record_test_result(
    *, run_case_id, project_id, status, executed_by=None, actual_result=None, duration_ms=None
):
    try:
        run_case = (
            TestRunCase.objects.select_for_update()
            .select_related("test_run", "project", "workspace")
            .get(id=run_case_id, project_id=project_id)
        )
    except TestRunCase.DoesNotExist as exc:
        raise ObjectDoesNotExist("The run case does not exist in this project.") from exc
    if run_case.test_run.status == "completed":
        raise ValidationError("Completed test runs do not accept new results.")
    if status not in dict(TestResult.STATUS_CHOICES):
        raise ValidationError("Unsupported test result status.")
    sequence = run_case.results.aggregate(value=Max("sequence"))["value"] or 0
    result = TestResult.objects.create(
        project=run_case.project,
        workspace=run_case.workspace,
        run_case=run_case,
        sequence=sequence + 1,
        status=status,
        actual_result=actual_result or {},
        duration_ms=duration_ms,
        executed_by=executed_by,
    )
    TestRunCase.objects.filter(id=run_case.id).update(latest_status=status)
    return result


@transaction.atomic
def create_defect_from_result(*, result_id, run_case_id, project_id, created_by, name=None, priority="high"):
    try:
        result = (
            TestResult.objects.select_for_update()
            .select_related(
                "run_case__test_run",
                "run_case__test_case",
                "run_case__test_case_version",
                "project",
                "workspace",
            )
            .get(id=result_id, run_case_id=run_case_id, project_id=project_id)
        )
    except TestResult.DoesNotExist as exc:
        raise ObjectDoesNotExist("The test result does not exist in this run case.") from exc
    if result.status not in ("failed", "blocked"):
        raise ValidationError("Defects can only be created from failed or blocked results.")

    run_case = result.run_case
    version = run_case.test_case_version
    defect_name = (name or f"[TC-{run_case.test_case.sequence}] {version.title}").strip()
    if not defect_name:
        raise ValidationError("A defect name is required.")
    actual_payload = result.actual_result if isinstance(result.actual_result, dict) else {}
    actual = actual_payload.get("text", "") if actual_payload else str(result.actual_result)
    # Rich content survives the handover when it exists. Flattening everything to
    # plain text is what left a developer unable to reproduce from the defect alone.
    actual_html = actual_payload.get("html") if isinstance(actual_payload.get("html"), str) else None
    measured = actual_payload.get("measured")
    measurement_html = (
        f"<p><strong>Measured:</strong> {escape(str(measured))} "
        f"{escape(str(actual_payload.get('unit', '')))}</p>"
        if measured is not None
        else ""
    )
    artifacts = actual_payload.get("artifacts")
    artifacts_html = (
        "<p><strong>Artifacts:</strong> "
        + ", ".join(f'<a href="{escape(str(item))}">{escape(str(item))}</a>' for item in artifacts)
        + "</p>"
        if isinstance(artifacts, list) and artifacts
        else ""
    )
    preconditions = (
        version.preconditions.get("text", "")
        if isinstance(version.preconditions, dict)
        else str(version.preconditions)
    )
    environment = json.dumps(run_case.test_run.configuration, ensure_ascii=False, sort_keys=True)
    app_base_url = (settings.APP_BASE_URL or settings.WEB_URL or "").rstrip("/")
    # Addressable since #11, so the defect points at the exact execution that
    # produced it rather than at the Testing tab in general.
    source_url = (
        f"{app_base_url}/{result.workspace.slug}/projects/{project_id}"
        f"/testing/runs/{run_case.test_run_id}/{run_case.id}"
        if app_base_url
        else ""
    )
    case_url = (
        f"{app_base_url}/{result.workspace.slug}/projects/{project_id}"
        f"/testing/cases/{run_case.test_case.sequence}"
        if app_base_url
        else ""
    )
    source_html = (
        f'<p><strong>Source:</strong> <a href="{escape(source_url)}">'
        f"Open this execution</a> · "
        f'<a href="{escape(case_url)}">TC-{run_case.test_case.sequence}</a></p>'
        if source_url
        else ""
    )
    steps = "".join(
        f"<li>{escape(str(step.action.get('text', step.action)))}"
        f"<br><strong>Expected:</strong> {escape(str(step.expected_result.get('text', step.expected_result)))}</li>"
        for step in version.steps.all()
    )
    description_html = (
        f"<p><strong>Test run:</strong> {escape(run_case.test_run.name)}</p>"
        f"<p><strong>Build:</strong> {escape(run_case.test_run.build or '—')}</p>"
        f"<p><strong>Environment:</strong> {escape(environment or '{}')}</p>"
        f"<p><strong>Preconditions:</strong> {escape(preconditions or '—')}</p>"
        f"<p><strong>Actual result:</strong></p>"
        f"{actual_html or f'<p>{escape(actual) if actual else chr(8212)}</p>'}"
        f"{measurement_html}"
        f"{artifacts_html}"
        f"{source_html}"
        f"<ol>{steps}</ol>"
    )
    issue = Issue.objects.create(
        project=result.project,
        workspace=result.workspace,
        name=defect_name[:255],
        description_html=description_html,
        description_json={
            "source": "testing",
            "test_result_id": str(result.id),
            "test_run_id": str(run_case.test_run_id),
            "run_case_id": str(run_case.id),
            "actual_result": result.actual_result,
            "environment": run_case.test_run.configuration,
            "preconditions": version.preconditions,
            "source_url": source_url,
            "case_url": case_url,
        },
        priority=priority,
        created_by=created_by,
    )
    link = TestResultIssueLink(
        project=result.project,
        workspace=result.workspace,
        test_result=result,
        issue=issue,
        created_by=created_by,
    )
    _validate_domain_model(link)
    link.save()
    return link


@transaction.atomic
def close_test_run(*, test_run_id, project_id):
    test_run = TestRun.objects.select_for_update().get(id=test_run_id, project_id=project_id)
    if test_run.status != "completed":
        test_run.status = "completed"
        test_run.closed_at = timezone.now()
        test_run.save(update_fields=["status", "closed_at", "updated_at"])
    return test_run
