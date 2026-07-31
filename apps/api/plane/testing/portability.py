# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import csv
import io
import json

from django.core.exceptions import ValidationError
from django.db import transaction

from plane.db.models import Issue, Project, TestCase, TestFolder

from .services import create_test_case, link_test_case_to_work_item


CSV_FIELDS = (
    "case_sequence",
    "folder_path",
    "title",
    "description_json",
    "preconditions_json",
    "priority",
    "tags_json",
    "step_position",
    "action_json",
    "expected_result_json",
    "work_item_sequences",
)


def _folder_path(folder):
    names = []
    seen = set()
    while folder:
        if folder.id in seen:
            raise ValidationError("A cycle exists in the test folder hierarchy.")
        seen.add(folder.id)
        names.append(folder.name)
        folder = folder.parent
    return "/".join(reversed(names))


def export_test_library_csv(*, project_id):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
    writer.writeheader()
    cases = (
        TestCase.objects.filter(project_id=project_id, archived_at__isnull=True)
        .select_related("folder")
        .prefetch_related("folder__parent", "versions__steps", "work_item_links__issue")
    )
    for test_case in cases:
        version = next(item for item in test_case.versions.all() if item.version == test_case.current_version)
        steps = list(version.steps.all()) or [None]
        work_items = ";".join(str(link.issue.sequence_id) for link in test_case.work_item_links.all())
        for step in steps:
            writer.writerow(
                {
                    "case_sequence": test_case.sequence,
                    "folder_path": _folder_path(test_case.folder),
                    "title": version.title,
                    "description_json": json.dumps(version.description, ensure_ascii=False, separators=(",", ":")),
                    "preconditions_json": json.dumps(version.preconditions, ensure_ascii=False, separators=(",", ":")),
                    "priority": version.priority,
                    "tags_json": json.dumps(version.tags, ensure_ascii=False, separators=(",", ":")),
                    "step_position": step.position if step else "",
                    "action_json": json.dumps(step.action, ensure_ascii=False, separators=(",", ":")) if step else "",
                    "expected_result_json": json.dumps(
                        step.expected_result, ensure_ascii=False, separators=(",", ":")
                    )
                    if step
                    else "",
                    "work_item_sequences": work_items,
                }
            )
    return output.getvalue()


def _json_value(row, field, default):
    raw = row.get(field, "").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid JSON in {field}: {exc}") from exc


@transaction.atomic
def import_test_library_csv(*, project_id, csv_text, created_by=None):
    if len(csv_text.encode("utf-8")) > 10 * 1024 * 1024:
        raise ValidationError("CSV exceeds the 10 MiB import limit.")
    project = Project.objects.select_for_update().get(id=project_id)
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames or not set(CSV_FIELDS).issubset(reader.fieldnames):
        raise ValidationError(f"CSV must contain: {', '.join(CSV_FIELDS)}")
    grouped = {}
    for index, row in enumerate(reader, start=2):
        key = row.get("case_sequence", "").strip()
        if not key:
            raise ValidationError(f"Row {index} has no case_sequence.")
        grouped.setdefault(key, []).append(row)
    folders = {"": None}

    def resolve_folder(path):
        path = path.strip().strip("/")
        if path in folders:
            return folders[path]
        parent = None
        current_path = ""
        for name in path.split("/"):
            name = name.strip()
            if not name or name in (".", ".."):
                raise ValidationError(f"Invalid folder path: {path}")
            current_path = f"{current_path}/{name}".strip("/")
            if current_path not in folders:
                folder, _created = TestFolder.objects.get_or_create(
                    project=project,
                    workspace=project.workspace,
                    parent=parent,
                    name=name,
                    defaults={"created_by": created_by},
                )
                folders[current_path] = folder
            parent = folders[current_path]
        return parent

    diagnostics = []
    created_cases = []
    for source_sequence, rows in grouped.items():
        first = rows[0]
        steps = []
        for row in sorted(rows, key=lambda item: int(item.get("step_position") or 0)):
            if row.get("step_position", "").strip():
                steps.append(
                    {
                        "action": _json_value(row, "action_json", {}),
                        "expected_result": _json_value(row, "expected_result_json", {}),
                    }
                )
        test_case = create_test_case(
            project_id=project.id,
            title=first["title"],
            folder_id=getattr(resolve_folder(first.get("folder_path", "")), "id", None),
            description=_json_value(first, "description_json", {}),
            preconditions=_json_value(first, "preconditions_json", {}),
            priority=first.get("priority") or "none",
            tags=_json_value(first, "tags_json", []),
            steps=steps,
        )
        created_cases.append(test_case)
        for sequence in filter(None, first.get("work_item_sequences", "").split(";")):
            issue = Issue.objects.filter(project=project, sequence_id=sequence.strip()).first()
            if issue:
                link_test_case_to_work_item(test_case_id=test_case.id, issue_id=issue.id, project_id=project.id)
            else:
                diagnostics.append(
                    {"code": "work_item_not_found", "case_sequence": source_sequence, "work_item_sequence": sequence}
                )
    return {
        "created": len(created_cases),
        "diagnostics": diagnostics,
        "case_ids": [str(item.id) for item in created_cases],
    }
