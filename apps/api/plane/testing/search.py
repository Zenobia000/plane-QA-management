# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import csv
import io
import json
import shlex
from html import escape

from django.core.exceptions import ValidationError
from django.utils.html import strip_tags
from openpyxl import Workbook

from plane.db.models import Issue, Project, TestCase


SEARCH_SCOPES = {"all", "test_cases", "work_items"}
EXPORT_FORMATS = {"csv", "html", "excel"}
MAX_SEARCH_SCAN = 5000
QUERY_FIELDS = {"type", "id", "title", "priority", "status", "tag", "folder"}
EXPORT_FIELDS = (
    "record_type",
    "identifier",
    "title",
    "description",
    "preconditions",
    "steps",
    "priority",
    "status",
    "folder",
    "tags",
    "linked_records",
    "updated_at",
)


def _document_text(value):
    if isinstance(value, dict) and isinstance(value.get("text"), str):
        return value["text"]
    if value in ({}, [], None, ""):
        return ""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _folder_path(folder):
    names = []
    seen = set()
    while folder:
        if folder.id in seen:
            break
        seen.add(folder.id)
        names.append(folder.name)
        folder = folder.parent
    return "/".join(reversed(names))


def _parse_query(query):
    if len(query) > 500:
        raise ValidationError("Query must be 500 characters or fewer.")
    try:
        tokens = shlex.split(query)
    except ValueError as exc:
        raise ValidationError(f"Invalid query syntax: {exc}") from exc
    if len(tokens) > 30:
        raise ValidationError("Query must contain 30 terms or fewer.")

    filters = []
    terms = []
    for token in tokens:
        if token.upper() == "AND":
            continue
        if ":" not in token:
            terms.append(token.casefold())
            continue
        field, value = token.split(":", 1)
        field = field.casefold().strip()
        value = value.casefold().strip()
        if field not in QUERY_FIELDS:
            allowed = ", ".join(sorted(QUERY_FIELDS))
            raise ValidationError(f"Unknown query field '{field}'. Allowed fields: {allowed}.")
        if not value:
            raise ValidationError(f"Query field '{field}' requires a value.")
        filters.append((field, value))
    return filters, terms


def _matches(record, filters, terms):
    searchable = " ".join(
        str(record.get(field, ""))
        for field in (
            "identifier",
            "title",
            "description",
            "preconditions",
            "steps",
            "priority",
            "status",
            "state_group",
            "work_item_type",
            "folder",
            "tags",
        )
    ).casefold()
    if any(term not in searchable for term in terms):
        return False

    for field, value in filters:
        if field == "type":
            aliases = {
                "case": "test_case",
                "testcase": "test_case",
                "test-case": "test_case",
                "issue": "work_item",
                "task": "work_item",
                "work-item": "work_item",
                "test_cases": "test_case",
                "work_items": "work_item",
            }
            if aliases.get(value, value) != record["kind"]:
                return False
        elif field == "tag":
            if value not in [tag.casefold() for tag in record.get("tags", [])]:
                return False
        elif field == "id":
            if value not in record["identifier"].casefold() and value != record["id"].casefold():
                return False
        elif field == "status":
            status_value = f"{record.get('status', '')} {record.get('state_group', '')}".casefold()
            if value not in status_value:
                return False
        elif value not in str(record.get(field, "")).casefold():
            return False
    return True


def _test_case_records(project_id):
    cases = (
        TestCase.objects.filter(project_id=project_id, archived_at__isnull=True)
        .select_related("folder", "folder__parent")
        .prefetch_related("versions__steps", "work_item_links__issue", "run_cases__test_run")
    )
    records = []
    for test_case in cases[:MAX_SEARCH_SCAN]:
        version = next(
            (item for item in test_case.versions.all() if item.version == test_case.current_version),
            None,
        )
        if version is None:
            continue
        latest_run_case = max(
            test_case.run_cases.all(),
            key=lambda item: item.test_run.created_at,
            default=None,
        )
        work_items = list(test_case.work_item_links.all())
        steps = [
            f"{step.position}. {_document_text(step.action)} => {_document_text(step.expected_result)}"
            for step in version.steps.all()
        ]
        records.append(
            {
                "kind": "test_case",
                "id": str(test_case.id),
                "identifier": f"TC-{test_case.sequence}",
                "sequence": test_case.sequence,
                "title": version.title,
                "description": _document_text(version.description),
                "preconditions": _document_text(version.preconditions),
                "steps": "\n".join(steps),
                "priority": version.priority,
                "status": latest_run_case.latest_status if latest_run_case else "unexecuted",
                "folder": _folder_path(test_case.folder),
                "tags": version.tags,
                "linked_record_ids": [str(link.issue_id) for link in work_items],
                "linked_records": [f"{link.issue.project.identifier}-{link.issue.sequence_id}" for link in work_items],
                "updated_at": test_case.updated_at.isoformat(),
            }
        )
    return records


def _work_item_records(project):
    issues = (
        Issue.objects.filter(project=project, archived_at__isnull=True)
        .select_related("state", "type")
        .prefetch_related("test_case_links__test_case")
    )
    records = []
    for issue in issues[:MAX_SEARCH_SCAN]:
        linked_cases = list(issue.test_case_links.all())
        records.append(
            {
                "kind": "work_item",
                "id": str(issue.id),
                "identifier": f"{project.identifier}-{issue.sequence_id}",
                "sequence": issue.sequence_id,
                "title": issue.name,
                "description": issue.description_stripped or strip_tags(issue.description_html or ""),
                "preconditions": "",
                "steps": "",
                "priority": issue.priority,
                "status": issue.state.name if issue.state else "unassigned",
                "state_group": issue.state.group if issue.state else None,
                "folder": "",
                "tags": [],
                "work_item_type": issue.type.name if issue.type else None,
                "linked_record_ids": [str(link.test_case_id) for link in linked_cases],
                "linked_records": [f"TC-{link.test_case.sequence}" for link in linked_cases],
                "updated_at": issue.updated_at.isoformat(),
            }
        )
    return records


def search_testing_records(*, project_id, query="", scope="all", limit=200):
    if scope not in SEARCH_SCOPES:
        raise ValidationError(f"Invalid scope. Choose one of: {', '.join(sorted(SEARCH_SCOPES))}.")
    if limit < 1 or limit > 200:
        raise ValidationError("Limit must be between 1 and 200.")
    filters, terms = _parse_query(query.strip())
    project = Project.objects.get(id=project_id)

    records = []
    if scope in ("all", "test_cases"):
        records.extend(_test_case_records(project_id))
    if scope in ("all", "work_items"):
        records.extend(_work_item_records(project))
    matched = [record for record in records if _matches(record, filters, terms)]
    matched.sort(key=lambda item: (item["kind"], item["sequence"]))
    return matched[:limit]


def _export_row(record):
    return {
        "record_type": record["kind"],
        "identifier": record["identifier"],
        "title": record["title"],
        "description": record["description"],
        "preconditions": record["preconditions"],
        "steps": record["steps"],
        "priority": record["priority"],
        "status": record["status"],
        "folder": record["folder"],
        "tags": ";".join(record["tags"]),
        "linked_records": ";".join(record["linked_records"]),
        "updated_at": record["updated_at"],
    }


def export_testing_records(*, records, export_format):
    if export_format not in EXPORT_FORMATS:
        raise ValidationError(f"Invalid format. Choose one of: {', '.join(sorted(EXPORT_FORMATS))}.")
    rows = [_export_row(record) for record in records]
    if export_format == "csv":
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue(), "text/csv; charset=utf-8", "plane-testing-search.csv"

    if export_format == "excel":
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Testing search"
        worksheet.append(list(EXPORT_FIELDS))
        for row in rows:
            worksheet.append([row[field] for field in EXPORT_FIELDS])
        output = io.BytesIO()
        workbook.save(output)
        return (
            output.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "plane-testing-search.xlsx",
        )

    heading = "Plane Testing search export"
    table_head = "".join(f"<th>{escape(field)}</th>" for field in EXPORT_FIELDS)
    table_rows = "".join(
        "<tr>" + "".join(f"<td>{escape(str(row[field]))}</td>" for field in EXPORT_FIELDS) + "</tr>" for row in rows
    )
    styles = (
        "body{font-family:Arial,sans-serif}"
        "table{border-collapse:collapse}"
        "th,td{border:1px solid #bbb;padding:6px;text-align:left;vertical-align:top}"
        "th{background:#eee}"
    )
    document = (
        '<!doctype html><html><head><meta charset="utf-8"><title>'
        + heading
        + "</title><style>"
        + styles
        + "</style></head><body><h1>"
        + heading
        + "</h1><table><thead><tr>"
        + table_head
        + "</tr></thead><tbody>"
        + table_rows
        + "</tbody></table></body></html>"
    )
    return document, "text/html; charset=utf-8", "plane-testing-search.html"
