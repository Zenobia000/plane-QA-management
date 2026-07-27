---
name: plane-qa
description: Operate integrated Plane project management and QA through the plane-qa MCP server or CLI. Use for project context, work-item lifecycle, custom work-item types/properties, milestones, initiatives, test libraries, traceability, test runs, defects, quality gates, and CI result ingestion.
---

# Plane QA

Use one project scope for both delivery work and test evidence. Prefer MCP tools when available; use `plane-qa` CLI for shell automation and CI.

## Start safely

1. Call `project_get_context` before writes. Resolve identifiers; never guess UUIDs or state IDs.
2. Read current issue, case, run, or quality state before changing it.
3. Keep work-item updates and QA evidence linked within the same project.
4. Request confirmation for archive, delete, unlink, or run close. Use CLI `--dry-run` when previewing.
5. Never request, print, paste, or commit `PLANE_API_KEY`.

## Configure delivery structure

Before creating work items that need a custom type or required property, create and inspect the project configuration first:

1. Use `create_work_item_type` to create a workspace type and enable it for one project.
2. Use `create_work_item_property` for a project-scoped field. Select properties require explicit option values.
3. Create a milestone with `create_milestone`; it belongs to exactly one project.
4. Create a workspace-level `create_initiative` only when the outcome spans projects. Pass project UUIDs from the same workspace only.
5. Supply required property values in a work-item `properties` object keyed by property UUID. Do not bypass a required field by writing directly to the database.

Type, property, milestone, and project IDs are scope-sensitive. Read or resolve them first; never reuse an ID from another project or workspace.

## Preserve evidence

- Treat test-case updates as new immutable versions.
- Remember that a fixed run pins its selected case versions.
- Append test results; do not rewrite prior failures or passes.
- Use a stable idempotency key for each logical automation upload and reuse it for retries.
- Inspect `quality_release_gate` before claiming release readiness.

## Choose a workflow

- For delivery-structure setup, issue lifecycle, failed-test defect/retest, release checks, or CI triage, read [workflows.md](references/workflows.md).
- For exact MCP tool and CLI command mappings, inputs, exit codes, and safety classes, read [tooling.md](references/tooling.md).
- For PM/QA job-to-be-done playbooks (sprint planning, test library design, run execution), read [role-playbooks.md](references/role-playbooks.md).
- For raw REST endpoints and payloads, read [api-reference.md](references/api-reference.md); for modifying the platform itself, read [codebase-map.md](references/codebase-map.md).

If a write fails, report the stable error category and request identifier. Re-read state before retrying conflicts; do not broaden permissions or bypass confirmation.
