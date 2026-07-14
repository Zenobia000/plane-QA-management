# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import close_old_connections

from plane.db.models import Project, TestAutomationIngestion, TestCase, TestResult, TestRun
from plane.testing import create_fixed_test_run, create_test_case, ingest_automation_results, record_test_result


def _thread_call(function, **kwargs):
    close_old_connections()
    try:
        return function(**kwargs)
    finally:
        close_old_connections()


@pytest.mark.django_db(transaction=True)
def test_concurrent_case_creation_allocates_unique_project_sequences(workspace, create_user):
    project = Project.objects.create(name="Concurrent cases", identifier="CC", workspace=workspace, created_by=create_user)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(_thread_call, create_test_case, project_id=project.id, title=f"Case {index}")
            for index in range(2)
        ]
        [future.result() for future in futures]
    assert list(TestCase.objects.filter(project=project).order_by("sequence").values_list("sequence", flat=True)) == [1, 2]


@pytest.mark.django_db(transaction=True)
def test_concurrent_results_append_unique_sequences(workspace, create_user):
    project = Project.objects.create(name="Concurrent results", identifier="CR", workspace=workspace, created_by=create_user)
    test_case = create_test_case(project_id=project.id, title="Retest")
    run = create_fixed_test_run(project_id=project.id, name="Concurrent run", test_case_ids=[test_case.id])
    run_case = run.run_cases.get()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                _thread_call,
                record_test_result,
                run_case_id=run_case.id,
                project_id=project.id,
                status=status,
            )
            for status in ("failed", "passed")
        ]
        [future.result() for future in futures]
    assert list(TestResult.objects.filter(run_case=run_case).order_by("sequence").values_list("sequence", flat=True)) == [
        1,
        2,
    ]


@pytest.mark.django_db(transaction=True)
def test_concurrent_identical_ingestion_creates_one_run(workspace, create_user):
    project = Project.objects.create(name="Concurrent CI", identifier="CI", workspace=workspace, created_by=create_user)
    kwargs = {
        "project_id": project.id,
        "idempotency_key": "same-upload",
        "source": "ci",
        "name": "CI upload",
        "results": [{"external_id": "stable", "status": "passed"}],
    }
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(_thread_call, ingest_automation_results, **kwargs) for _index in range(2)]
        outcomes = [future.result() for future in futures]
    assert sorted(replayed for _ingestion, replayed in outcomes) == [False, True]
    assert TestAutomationIngestion.objects.filter(project=project).count() == 1
    assert TestRun.objects.filter(project=project).count() == 1
