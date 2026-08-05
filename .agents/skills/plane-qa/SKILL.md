---
name: plane-qa
description: Operate integrated Plane project management and QA through the plane-qa MCP server or CLI. Use for project context, work-item lifecycle, custom work-item types/properties, milestones, initiatives, intake triage, test libraries, traceability, test runs, defects, quality gates, and CI result ingestion.
---

# Plane QA

Use one project scope for both delivery work and test evidence. Prefer MCP tools when available; use `plane-qa` CLI for shell automation and CI.

## Know which surface you can reach

The fork has a browser-only product war room — the Project Overview, its noticeboard, the customer frontline panel and the overdue/urgent shortlist. Those routes live under `/api/workspaces/...` with session auth and have **no `/api/v1` equivalent and no MCP tool**, so an API key gets 404 there, which reads like a missing project rather than a missing tree.

That does not put the surface out of reach. Everything it displays is read from entities you can write over `/api/v1`: file and attribute intake so it appears in the frontline panel, set a `target_date` or `urgent` priority so an item reaches the attention list, create the labels a team files announcements under. See the app-tree note in [api-reference.md](references/api-reference.md) for the mapping. The exception is posting announcements: `updates/` has no API-key route at all. Treat that as a property to preserve rather than a gap to close — a board that fills itself with generated status is the thing that surface was built to replace. If the user wants an announcement made, draft the text and tell them where it goes.

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

## Know the model before you add to it

Four facts decide whether a write lands where the product will read it. All four have been got
wrong in this codebase before, and each mistake is still visible in a repair command or an ADR.

- **The breakdown ships with five types** — Epic (level 0), Feature (1), Story (2), Bug (2),
  Task (3) — and types are workspace-wide. `list` before you create; a hand-typed name becomes a
  second vocabulary for a tier that already exists.
- **Requirement nature is `Issue.requirement_kind`** (`functional` / `quality` / `none`), not a
  type and not a custom property. A type already carries breadth through `level`, so making it
  carry nature multiplies the two axes; a property is per-project, so no cross-project report could
  ask the question. It is writable on `/api/v1` only — no CLI flag, no MCP input, no UI control.
- **`IssueType.needs_acceptance` decides who owes a test.** Types created through MCP default to
  `true`, so a type meant for implementation work will demand acceptance contracts until it is
  patched to `false`.
- **States are data, and a project may hold 14 of them** with nine sharing the `started` group.
  Resolve a state by name; a lookup keyed by group returns whichever row came last.

## Read the project's vocabulary; do not assume one

No category name is compiled into this product. Announcement topics are the project's own `Label`s, and the frontline panel groups by whichever `WorkItemProperty` a project marked as its dimension — customer for one team, tenant or region for the next. So:

- Resolve label and property **UUIDs** from the project before writing. A name you remember from another project is not a name this one has.
- When a task says "tag this as a customer issue", find the property that actually holds customers rather than creating one called Customer. Creating a second is how a project ends up with two vocabularies and neither complete.
- At most one property per project can be the grouping dimension, and only `select`/`multi_select` qualifies. Marking one is a human decision made in settings; do not flip it to make your output render.

## Preserve evidence

- Treat test-case updates as new immutable versions.
- Remember that a fixed run pins its selected case versions.
- Append test results; do not rewrite prior failures or passes.
- Use a stable idempotency key for each logical automation upload and reuse it for retries.
- Inspect `quality_release_gate` before claiming release readiness.

## Choose a workflow

- For delivery-structure setup, issue lifecycle, failed-test defect/retest, release checks, CI triage, or the field-report-to-backlog path, read [workflows.md](references/workflows.md).
- For exact MCP tool and CLI command mappings, inputs, exit codes, and safety classes, read [tooling.md](references/tooling.md).
- For PM / QA / product job-to-be-done playbooks (sprint planning, test library design, run execution, field-report triage), read [role-playbooks.md](references/role-playbooks.md).
- For raw REST endpoints and payloads, read [api-reference.md](references/api-reference.md); for modifying the platform itself, read [codebase-map.md](references/codebase-map.md).
- For seeding, refreshing, or reading a demo project — and for the repair commands that undo a
  drifted vocabulary — read [demo-data.md](references/demo-data.md). `--force` re-seeding deletes a
  project; never point it at one holding hand-written data.

If a write fails, report the stable error category and request identifier. Re-read state before retrying conflicts; do not broaden permissions or bypass confirmation.
