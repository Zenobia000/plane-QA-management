# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import hashlib
import json
from xml.etree import ElementTree

from django.core.exceptions import ValidationError
from django.db import transaction

from plane.db.models import (
    Project,
    TestAutomationIngestion,
    TestCase,
    TestCaseAutomationLink,
)

from .services import create_fixed_test_run, create_test_case, record_test_result


class IdempotencyConflict(Exception):
    pass


def serialize_ingestion_response(ingestion, replayed):
    run = ingestion.test_run
    counts = {"passed": 0, "failed": 0, "blocked": 0, "skipped": 0, "open": 0}
    for run_case in run.run_cases.all():
        counts[run_case.latest_status] += 1
    return {
        "id": str(ingestion.id),
        "idempotency_key": ingestion.idempotency_key,
        "replayed": replayed,
        "test_run": {"id": str(run.id), "name": run.name, "status": run.status, **counts},
        "diagnostics": ingestion.diagnostics,
    }


def parse_junit_xml(xml_text):
    if len(xml_text.encode("utf-8")) > 5 * 1024 * 1024:
        raise ValidationError("JUnit XML exceeds the 5 MiB ingestion limit.")
    upper = xml_text.upper()
    if "<!DOCTYPE" in upper or "<!ENTITY" in upper:
        raise ValidationError("DTD and entity declarations are not allowed in JUnit XML.")
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise ValidationError(f"Invalid JUnit XML: {exc}") from exc
    results = []
    for node in root.iter("testcase"):
        classname = node.attrib.get("classname", "").strip()
        name = node.attrib.get("name", "Unnamed test").strip()
        external_id = f"{classname}::{name}" if classname else name
        failure = node.find("failure")
        error = node.find("error")
        skipped = node.find("skipped")
        status = "failed" if failure is not None or error is not None else "skipped" if skipped is not None else "passed"
        evidence = failure if failure is not None else error if error is not None else skipped
        actual = {}
        if evidence is not None:
            actual = {
                "text": (evidence.text or evidence.attrib.get("message", "")).strip(),
                "type": evidence.attrib.get("type", ""),
            }
        try:
            duration_ms = round(float(node.attrib.get("time", "0")) * 1000)
        except ValueError:
            duration_ms = None
        results.append(
            {
                "external_id": external_id,
                "title": f"{classname} · {name}" if classname else name,
                "status": status,
                "duration_ms": duration_ms,
                "actual_result": actual,
            }
        )
    if not results:
        raise ValidationError("JUnit XML contains no testcase elements.")
    return results


def canonical_payload_hash(payload):
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@transaction.atomic
def ingest_automation_results(
    *, project_id, idempotency_key, source, name, results, build="", configuration=None, artifact_ids=None, created_by=None
):
    project = Project.objects.select_for_update().get(id=project_id)
    normalized = {
        "source": source,
        "name": name,
        "build": build,
        "configuration": configuration or {},
        "results": results,
        "artifact_ids": [str(item) for item in (artifact_ids or [])],
    }
    payload_hash = canonical_payload_hash(normalized)
    existing = TestAutomationIngestion.objects.select_related("test_run").filter(
        project=project, idempotency_key=idempotency_key
    ).first()
    if existing:
        if existing.payload_hash != payload_hash:
            raise IdempotencyConflict("The idempotency key was already used with a different payload.")
        return existing, True

    diagnostics = []
    accepted = []
    allowed_statuses = {"passed", "failed", "blocked", "skipped"}
    seen_external_ids = set()
    for index, item in enumerate(results):
        external_id = str(item.get("external_id", "")).strip()
        status = item.get("status")
        if not external_id or status not in allowed_statuses:
            diagnostics.append({"index": index, "code": "invalid_result", "external_id": external_id})
            continue
        if external_id in seen_external_ids:
            diagnostics.append({"index": index, "code": "duplicate_external_id", "external_id": external_id})
            continue
        seen_external_ids.add(external_id)
        link = TestCaseAutomationLink.objects.select_related("test_case").filter(
            project=project, source=source, external_id=external_id
        ).first()
        if link:
            test_case = link.test_case
        else:
            supplied_case_id = item.get("test_case_id")
            test_case = (
                TestCase.objects.filter(id=supplied_case_id, project=project, archived_at__isnull=True).first()
                if supplied_case_id
                else None
            )
            if not test_case:
                test_case = create_test_case(
                    project_id=project.id,
                    title=str(item.get("title") or external_id)[:500],
                    tags=["automated"],
                )
                diagnostics.append({"index": index, "code": "test_case_created", "external_id": external_id})
            automation_link = TestCaseAutomationLink(
                project=project,
                workspace=project.workspace,
                test_case=test_case,
                source=source,
                external_id=external_id,
                created_by=created_by,
            )
            automation_link.full_clean(exclude=("created_by", "updated_by"))
            automation_link.save()
        accepted.append((test_case, item))
    if not accepted:
        raise ValidationError("No valid automation results were supplied.")

    test_run = create_fixed_test_run(
        project_id=project.id,
        name=name,
        test_case_ids=[test_case.id for test_case, _item in accepted],
        build=build,
        configuration={**(configuration or {}), "automation_source": source},
    )
    run_cases = {str(item.test_case_id): item for item in test_run.run_cases.all()}
    for test_case, item in accepted:
        record_test_result(
            run_case_id=run_cases[str(test_case.id)].id,
            project_id=project.id,
            status=item["status"],
            actual_result=item.get("actual_result") or {},
            duration_ms=item.get("duration_ms"),
            executed_by=created_by,
        )
    ingestion = TestAutomationIngestion.objects.create(
        project=project,
        workspace=project.workspace,
        source=source,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        test_run=test_run,
        diagnostics=diagnostics,
        created_by=created_by,
    )
    if artifact_ids:
        from plane.bgtasks.testing_artifact_task import process_testing_artifacts

        transaction.on_commit(
            lambda: process_testing_artifacts.delay(str(ingestion.id), [str(item) for item in artifact_ids]),
            robust=True,
        )
    return ingestion, False
