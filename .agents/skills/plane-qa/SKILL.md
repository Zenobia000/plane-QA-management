---
name: plane-qa
description: Operate integrated Plane project management and QA through the plane-qa MCP server or CLI. Use for project context, work-item lifecycle, test libraries, traceability, test runs, defects, quality gates, and CI result ingestion.
---

# Plane QA

Use one project scope for both delivery work and test evidence. Prefer MCP tools when available; use `plane-qa` CLI for shell automation and CI.

## Start safely

1. Call `project_get_context` before writes. Resolve identifiers; never guess UUIDs or state IDs.
2. Read current issue, case, run, or quality state before changing it.
3. Keep work-item updates and QA evidence linked within the same project.
4. Request confirmation for archive, delete, unlink, or run close. Use CLI `--dry-run` when previewing.
5. Never request, print, paste, or commit `PLANE_API_KEY`.

## Preserve evidence

- Treat test-case updates as new immutable versions.
- Remember that a fixed run pins its selected case versions.
- Append test results; do not rewrite prior failures or passes.
- Use a stable idempotency key for each logical automation upload and reuse it for retries.
- Inspect `quality_release_gate` before claiming release readiness.

## Choose a workflow

- For issue lifecycle, failed-test defect/retest, release checks, or CI triage, read [workflows.md](references/workflows.md).
- For exact MCP tool and CLI command mappings, inputs, exit codes, and safety classes, read [tooling.md](references/tooling.md).
- For PM/QA job-to-be-done playbooks (sprint planning, test library design, run execution), read [role-playbooks.md](references/role-playbooks.md).
- For raw REST endpoints and payloads, read [api-reference.md](references/api-reference.md); for modifying the platform itself, read [codebase-map.md](references/codebase-map.md).

If a write fails, report the stable error category and request identifier. Re-read state before retrying conflicts; do not broaden permissions or bypass confirmation.
