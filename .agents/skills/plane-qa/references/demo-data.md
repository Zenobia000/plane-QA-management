# Plane QA — demo data

Two management commands build a whole project out of nothing: a work breakdown, a schedule, a
test library, executed runs, a defect loop, field reports and saved views. Use them to see the
model working end to end, to give a fresh instance something to show, or to reproduce a report
against data whose shape is known.

Neither is a test fixture. The pytest suite builds its own rows; these write to a real workspace
and are visible to everyone in it.

## Which seed

| Command                 | Identifier | Project                 | Built from                        | Reach for it when                                                                 |
| ----------------------- | ---------- | ----------------------- | --------------------------------- | --------------------------------------------------------------------------------- |
| `seed_testing_demo`     | `DEMO`     | Order Service Platform  | `plane/testing/demo/` (7 modules) | Anything about process, states, coverage, the Epics page, or the Project Overview |
| `seed_ai_software_demo` | `AIDEMO`   | AI DevFlow Copilot Demo | one 1,400-line command            | Showing every custom-property kind, or evidence attachments in object storage     |

`DEMO` is the canonical one and the project `docs/process/plane-qa-guideline.md` §B0 describes.
Its testing half goes through `plane.testing.services`, so the seeded rows are subject to the same
four invariants as production data — immutable versions, pinned run membership, append-only
results, defects only from failed or blocked results. Content is Traditional Chinese.

`AIDEMO` predates that package and still carries the default 5-state board. It is a feature
showcase, not a process model; `docs/demo/ai-software-delivery-demo.md` documents it in full.

## Running one

```bash
docker compose exec api python manage.py seed_testing_demo --workspace <slug>
docker compose exec api python manage.py seed_ai_software_demo --workspace <slug>
```

Shared flags: `--identifier` (defaults above), `--owner <email>` (defaults to the workspace owner,
and the command fails if the workspace has none), `--force`. `--skip-attachments` is AIDEMO-only —
it uploads two evidence files, so without MinIO/S3 reachable the run fails without it.

Each command prints what it built and the deep links to reach it — project overview, Epics page,
testing overview, cases, runs. Read that output rather than guessing what landed; the DEMO report
is counted from the rows it created, not restated from the design.

To bring the whole stack up first, see the `running-local-docker-stack` skill.

## `--force` is a delete, not a merge

Both commands refuse to run over an existing project of the same identifier. `--force` removes the
old one first, and it removes more than the project:

- the project, deleted one row at a time — a queryset `delete()` is a bulk soft-delete that never
  queues the cascade, and earlier runs left 17 cycles and 145 work items alive under projects the
  UI had already stopped showing
- saved views and pages belonging to **every** project that ever carried that identifier, including
  soft-deleted ones. Neither is swept by the project's own cascade, so they accumulate as orphans
  pointing at projects nobody can open
- the workspace-level initiative and the workspace-level view the seed owns, matched **by name** —
  they belong to the workspace, not the project, so nothing else would take them

There is no merge mode and the only thing matched on is the identifier. Never `--force` a project
holding hand-written data. If the demo has been edited by a person and you need a clean one, seed a
second identifier (`--identifier DEMO2`) instead.

## What `DEMO` is built to prove

Each piece exists to make one claim checkable, which is also what makes it a useful fixture to
reason against:

| Piece                                                                                                                             | The claim it makes checkable                                                                                                                     |
| --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| The `SDLC_STATES` set — 14 states as `states/` lists them (the default manager hides Triage), nine of them in the `started` group | State group and state name are different questions; `Wait to Release` is not `completed`, so a defect parked there still blocks the gate         |
| 5 epics across backlog / unstarted / started / cancelled                                                                          | The Epics page can group and lay out; the cancelled epic keeps its work in its own denominator, so dropped work does not read as nearly complete |
| Stories carrying parent, sprint, module, milestone, kind and labels                                                               | Six independent axes. No single hierarchy expresses them, which is why none of them is derived from another                                      |
| `requirement_kind` on items (`functional` / `quality` / `none`)                                                                   | Requirement nature crosses the breakdown instead of nesting under it — see B2 of the guideline                                                   |
| 4 custom properties (multi-select, boolean, date, number) plus a 5th marked as the grouping dimension                             | A property is a typed fact about the requirement, not a label and not part of the title                                                          |
| A closed sprint whose run pinned older case versions                                                                              | Library edits never reach a run that already started                                                                                             |
| A failure → defect → retest appended beside it                                                                                    | Results are append-only; a retest never overwrites the failure that caused it                                                                    |
| Intake reports under a project-chosen dimension + noticeboard posts                                                               | No category name is compiled in — the panel groups by whatever property the project marked                                                       |
| A page tree using `Page.is_folder`                                                                                                | A folder is declared, not inferred from having children (ADR 0007)                                                                               |
| A scheduled story with no contract                                                                                                | Definition of Ready has a violation to catch, and the release gate has something to block on                                                     |

## Reading a demo project as an agent

- **Resolve, never assume.** Identifiers are stable (`DEMO`, `AIDEMO`); every UUID in them is not.
  Start with `project_get_context`.
- **Match states by name, not by group.** `DEMO` puts nine states in `started`; a lookup keyed by
  group silently returns whichever row the queryset yielded last.
- **Coverage rows are not one per work item.** Only types with `needs_acceptance` produce a row
  (`Task` and `Bug` do not), rows in `backlog`/`cancelled` are out of scope, and a row that
  summarises other counted rows contributes nothing to the totals. An epic is not a second vote on
  its stories' coverage.
- **The Overview is browser-only.** Nothing you do over `/api/v1` reads those panels back; report
  what you wrote, not what the panel now shows. See the app-tree note in
  [api-reference.md](api-reference.md).

## Is the demo in front of you current?

The seed changes; the seeded project does not. A `DEMO` project created before a seed commit simply
lacks whatever that commit added — no error, no gap in the UI, just fewer rows than the docs
describe.

```bash
git log --oneline -5 -- apps/api/plane/testing/demo/     # when the seed last changed
```

Compare that against the project's creation date. If the seed moved since, re-seed with `--force`
after confirming nobody has hand-edited the project.

> This is not hypothetical. The local stack's `DEMO` spent two days seeded from a commit a few hours
> older than the field-report and five-epic changes, and presented as a working demo with 2 epics,
> no intake reports, no announcements and no grouping dimension — nothing looked broken, the panels
> simply had less to say. Re-seeded 2026-08-05.

"Hand-edited" is worth checking rather than assuming: compare each work item's `updated_at` against
the project's `created_at`, and read `IssueActivity` rows created after the seed. Field edits a
person made in the UI show up there with the author and the before/after values.

## Repair commands (not seeds)

Both default to reporting and change nothing until told otherwise — run them that way first.

| Command                                                        | Fixes                                                                                                                                                                                                                                                     |
| -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `converge_work_item_types --workspace <slug> [--apply]`        | A workspace that grew a hand-typed vocabulary beside the shipped one. Collapses it onto Epic/Feature/Story/Task/Bug and stamps `requirement_kind` from the old names. Never merges across workspaces, never deletes a type that still carries work items. |
| `sweep_orphaned_project_rows [--workspace <slug>] [--dry-run]` | Rows still alive under a soft-deleted project — including testing rows the normal cascade cannot save, because immutability guards refuse the write.                                                                                                      |
