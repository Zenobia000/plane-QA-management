# Plane QA — REST API reference

## Auth: two parallel URL trees, same handlers

| Tree   | Prefix                                                       | Auth                               | Consumers               |
| ------ | ------------------------------------------------------------ | ---------------------------------- | ----------------------- |
| Public | `/api/v1/workspaces/{slug}/projects/{project_uuid}/testing/` | `X-API-Key` header + rate throttle | SDK, CLI, MCP, CI, curl |
| App    | `/api/workspaces/{slug}/projects/{project_uuid}/testing/`    | Session cookie                     | Web UI only             |

Permissions (`ProjectEntityPermission`): reads need active project membership; writes need role ADMIN(20) or MEMBER(15). Non-member API key → 403.

## Domain model

```
Project
├─ TestFolder (tree via parent FK; unique(project,parent,name))
├─ TestCase (per-project sequence; current_version pointer; archived_at soft-archive)
│   ├─ TestCaseVersion (IMMUTABLE; unique version per case; title/description/preconditions/priority/tags)
│   │   └─ TestStep (IMMUTABLE; position; action; expected_result)
│   ├─ TestCaseWorkItemLink → Issue        (requirement coverage)
│   ├─ FileAsset(TESTING_ARTIFACT, entity_identifier=case UUID) (attachments)
│   └─ TestCaseAutomationLink              (unique(project,source,external_id) → maps CI results to cases)
├─ TestRun (status draft/active/completed; run_type fixed/live; build; configuration; cycle?; module?)
│   ├─ TestRunCase (pins test_case_version; latest_status open/passed/failed/blocked/skipped)
│   │   └─ TestResult (APPEND-ONLY; sequence; status passed/failed/blocked/skipped; actual_result; duration_ms)
│   │       └─ TestResultIssueLink → Issue (defect)
│   └─ TestAutomationIngestion (1:1 run; unique(project,idempotency_key); payload_hash; diagnostics)
```

All rows carry workspace/project FKs + audit fields + soft-delete; `clean()` enforces single-project consistency across every FK.

## Endpoints (both trees unless noted)

Paths relative to `.../testing/`.

| Method           | Path                                                  | Purpose / notes                                                                                                                                                                                                                                                                                                 |
| ---------------- | ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET              | `capabilities/`                                       | Feature flags (`enabled`, `stage`, capability booleans)                                                                                                                                                                                                                                                         |
| GET              | `overview/`                                           | Quality dashboard: coverage %, run counts, latest-run status counts, `open_defects`, per-run scorecards (≤10), `release_gate`                                                                                                                                                                                   |
| GET              | `requirement-coverage/`                               | Per-requirement coverage; multiple linked cases roll up worst-wins: `failed < blocked < open < skipped < passed`. **Not one row per work item** — see "Which work items owe a contract"                                                                                                                         |
| GET/POST         | `folders/`                                            | List / create (`name`, `parent_id?`, `sort_order?`)                                                                                                                                                                                                                                                             |
| GET/PATCH/DELETE | `folders/{folder_uuid}/`                              | PATCH rejects descendant-cycle moves (400); DELETE only if empty — no child folders and no non-archived cases (409 otherwise; empty it by moving cases to another folder via case PATCH `folder_id`, or archiving them, and deleting subfolders first)                                                          |
| GET/POST         | `test-cases/`                                         | List (filters `search`, `folder_id`, `work_item_id`; opt-in cursor pagination `per_page` ≤200, default 50) / create (`title` required, `folder_id?`, `priority?`, `steps?` = `[{action, expected_result}]`, `preconditions?`, `tags?`)                                                                          |
| GET/PATCH/DELETE | `test-cases/{case_uuid}/`                             | PATCH publishes a new immutable version and bumps `current_version`; DELETE soft-archives                                                                                                                                                                                                                       |
| GET/POST         | `test-cases/{case_uuid}/attachments/`                 | List confirmed attachments / create a presigned upload (`name`, allowlisted MIME `type`, `size` ≤ instance limit)                                                                                                                                                                                               |
| GET/PATCH/DELETE | `test-cases/{case_uuid}/attachments/{asset_uuid}/`    | Download or inline image preview / confirm storage upload / soft-delete                                                                                                                                                                                                                                         |
| GET              | `test-cases/{case_uuid}/versions/{int:version}/`      | Read any historical version + its steps                                                                                                                                                                                                                                                                         |
| GET/POST         | `test-cases/{case_uuid}/work-items/`                  | List / link requirement (`{"issue_id": "..."}`)                                                                                                                                                                                                                                                                 |
| DELETE           | `test-cases/{case_uuid}/work-items/{issue_uuid}/`     | Unlink                                                                                                                                                                                                                                                                                                          |
| GET/POST         | `test-runs/`                                          | List (filters `status`, `build`, `cycle_id`, `module_id`, `run_type`; `per_page` ≤100, default 25) / create fixed run (`{"name", "test_case_ids": [...], "build"?, "configuration"?, "cycle_id"?, "module_id"?}`) — dedupes ids, requires all cases active & in-project, pins current versions, starts `active` |
| GET              | `test-runs/{run_uuid}/`                               | Detail with run_cases, results, defects, progress                                                                                                                                                                                                                                                               |
| POST             | `test-runs/{run_uuid}/cases/{run_case_uuid}/results/` | Append result (`{"status", "actual_result"?, "duration_ms"?}`); updates `latest_status`; **rejected on completed runs**                                                                                                                                                                                         |
| POST             | `.../results/{result_uuid}/defects/`                  | Create defect Issue + atomic link; **only from failed/blocked results**; default priority `high`; description auto-built (run, build, env, steps, actual result)                                                                                                                                                |
| POST             | `test-runs/{run_uuid}/close/`                         | Set `completed` + `closed_at` (idempotent)                                                                                                                                                                                                                                                                      |
| POST             | `automation-ingestions/`                              | CI ingestion — see below                                                                                                                                                                                                                                                                                        |
| GET              | `search/?query=...&scope=all                          | test_cases                                                                                                                                                                                                                                                                                                      | work_items`      | Cross-entity search of active cases and Work Items. Controlled fields: `type`, `id`, `title`, `priority`, `status`, `tag`, `folder`; free terms use AND; ≤200 results |
| GET              | `export/?export_format=csv                            | html                                                                                                                                                                                                                                                                                                            | excel&query=...` | Export the same search/scope as UTF-8 CSV, standalone HTML, or real XLSX; includes case preconditions and steps                                                       |
| GET/POST         | `test-cases.csv`                                      | **App tree only.** CSV export / bulk import of the library (11-column schema, ≤10 MiB, creates folders from `folder_path`, links work items by `sequence_id`)                                                                                                                                                   |

The search syntax is a field-query DSL, not SQL. Unknown fields are rejected; arbitrary database statements are never executed. Example: `type:test_case priority:high tag:smoke "card payment"`.

### Write a case the way the editor reads it back

Storage is unchanged — `preconditions` plus ordered `(action, expected_result)` pairs — and it stays
that way because the execution workspace, the CSV export and the auto-built defect description all
read the three parts separately. What changed is the web editor: a case is now written and shown as
one Gherkin block, mapped `Given` → `preconditions`, each `When` → an `action`, the `Then` that
follows → that step's `expected_result`, with `And`/`But` and bare lines continuing whatever came
last.

Nothing about the payload changes, but a case authored over the API is displayed through that
mapping, so shape it to survive the round trip:

- Put setup in `preconditions`, not in the first step's `action` — it renders as `Given`.
- One action per step. Two actions crammed into one `action` come back as `When … And …`, which
  reads as one step with two halves rather than two steps.
- Multi-line values are fine: the second and later lines render as `And`.
- An `action` with an empty `expected_result` renders a `When` with no `Then`, which reads as an
  unfinished case.

## PM planning endpoints (upstream Plane, same `/api/v1` tree, X-API-Key)

Relative to `/api/v1/workspaces/{slug}/projects/{project_uuid}/` (outside `testing/`):

| Method                      | Path                                                         | Purpose                                                                                                                                                                           |
| --------------------------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET/POST · GET/PATCH/DELETE | `cycles/` · `cycles/{uuid}/`                                 | Sprints/time-boxes: `name`, `start_date`, `end_date` (`YYYY-MM-DD`)                                                                                                               |
| GET/POST · GET/DELETE       | `cycles/{cycle_uuid}/cycle-issues/` · `.../{issue_uuid}/`    | Add work items to a cycle: `{"issues": ["<uuid>", ...]}`                                                                                                                          |
| POST                        | `cycles/{cycle_uuid}/transfer-issues/`                       | Sprint rollover: `{"new_cycle_id": "..."}` — moves only incomplete work items, snapshots old-cycle progress                                                                       |
| POST                        | `cycles/{uuid}/archive/`                                     | Archive a cycle                                                                                                                                                                   |
| GET/POST · GET/PATCH/DELETE | `modules/` · `modules/{uuid}/`                               | Epics/capabilities                                                                                                                                                                |
| GET/POST · DELETE           | `modules/{module_uuid}/module-issues/` · `.../{issue_uuid}/` | Add work items to a module                                                                                                                                                        |
| GET/POST                    | `work-items/`, `labels/`, `states/`, `members/`              | Work items (fields incl. `start_date` ≤ `target_date`, `assignees` must be project members, `labels`, `requirement_kind`), plus supporting lookups                                |
| GET/POST · GET/PATCH/DELETE | `views/` · `views/{uuid}/`                                   | Saved views. Send `filters`; `query` is compiled from it server-side and a supplied one is ignored. PATCH on a locked view returns 409; DELETE requires ownership (403 otherwise) |

### States: resolve by name, and expect more than one per group

A project's states are data, not an enum, and a project seeded with the SDLC set carries 14 of them
— `Planning`, `In Design`, `In progress`, `In developing`, `PR Reviewing`, `In Diversity Testing`,
`PM Retest`, `Pending` and `Wait to Release` all share the `started` group. Code that maps group →
state silently keeps whichever row the queryset yielded last, so resolve the **name** from `states/`
and pass the UUID.

The group still decides four things, which is why the mapping is not cosmetic: coverage treats
every group except `backlog`/`cancelled` as owing a contract, the release gate counts a defect open
until its group is `completed` or `cancelled` (so a defect sitting in `Wait to Release` still
blocks), `completed_at` is stamped on entry to `completed`, and cycle progress counts
`completed + cancelled` as delivered.

### Workspace-scoped views

Relative to `/api/v1/workspaces/{slug}/` — the same handlers with no project segment:

| Method                      | Path                       | Purpose                                                                        |
| --------------------------- | -------------------------- | ------------------------------------------------------------------------------ |
| GET/POST · GET/PATCH/DELETE | `views/` · `views/{uuid}/` | Views spanning every project in the workspace; responses carry `project: null` |

Visibility for both scopes is the model's own rule, not the browser's: your views plus every `access: 1` (public) one. `access: 0` is private to its owner, and a key acts for its user.

Pages have no public endpoints. Their content is a Yjs CRDT document, so an HTML-only write is safe only for a page that has never been opened; that is out of scope here.

## CE work-item extensions

These are native to this fork's `/api/v1/` tree; do not call Plane commercial endpoints for them.

| Method                      | Path                                                                                          | Scope and purpose                                                                                                                                                      |
| --------------------------- | --------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | ---- | ------- | ------ | ------------ | ------------------------------------------- |
| GET/POST · GET/PATCH/DELETE | `/workspaces/{slug}/work-item-types/` · `.../work-item-types/{type_uuid}/`                    | Workspace type definitions: `name`, `level`, `is_epic`, `is_default`, `is_active`, `needs_acceptance`. POST/PATCH/DELETE requires an active workspace Admin or Member. |
| GET/POST · GET/PATCH/DELETE | `/workspaces/{slug}/projects/{project_uuid}/work-item-types/` · `.../{project_type_uuid}/`    | Enable/order/default a workspace type in one project. A Work Item may use only an enabled active type.                                                                 |
| GET/POST · GET/PATCH/DELETE | `/workspaces/{slug}/projects/{project_uuid}/work-item-properties/` · `.../{property_uuid}/`   | Project custom-property definitions. `kind` is `text                                                                                                                   | number | date | boolean | select | multi_select | url`; options require unique stable values. |
| GET · PUT/DELETE            | `.../work-items/{issue_uuid}/properties/` · `.../properties/{property_uuid}/`                 | Read, set, or clear a typed custom value. Property and work item must be in the same project.                                                                          |
| GET/POST · GET/PATCH/DELETE | `/workspaces/{slug}/projects/{project_uuid}/milestones/` · `.../milestones/{milestone_uuid}/` | Project delivery checkpoints. A Work Item `milestone` must be from its own project.                                                                                    |
| GET/POST · GET/PATCH/DELETE | `/workspaces/{slug}/initiatives/` · `.../initiatives/{initiative_uuid}/`                      | Workspace strategic outcomes, with optional same-workspace `project_ids`.                                                                                              |

Create or update a Work Item with custom values using `properties`, keyed by property UUID:

```json
{
  "name": "Validate checkout on Chrome",
  "type_id": "<enabled-work-item-type-uuid>",
  "milestone": "<same-project-milestone-uuid>",
  "properties": {
    "<browser-property-uuid>": "chrome",
    "<build-property-uuid>": "2026.7.27"
  }
}
```

Required active properties with no default must be present on Work Item creation. `select` accepts one option value; `multi_select` accepts a unique list of option values. Use `null` only for non-required properties.

### Parent and child levels

`IssueType.level` ranks a type by breadth, and **lower is broader**: Epic 0 → Feature 1 → Story 2
(Bug also 2) → Task 3. Work-item create/update refuses a parent narrower than its child
(`parent.level <= child.level`), so an Epic filed under a Task is a 400 naming both types.

The rule is deliberately not strict — a Bug (2) parented to the Story (2) it was found in is a real
modelling choice, not an inversion — and untyped work items are exempt, so a project that never
switched types on keeps saving. Upstream Plane numbers its two default types the other way round
(Task 0, Epic 1); this fork follows the seeded data, so do not carry an upstream example's numbers
across.

## Project Overview — app tree only, no API key reaches it

The overview is this fork's product war room: release readiness, progress, milestones, a noticeboard, intake grouped by customer, and the overdue/urgent shortlist. **Every one of these routes exists only under `/api/workspaces/...` with session auth.** There is no `/api/v1` mirror and no MCP tool. An API key gets 404, which reads like a missing project rather than a missing tree — check here before debugging permissions.

Relative to `/api/workspaces/{slug}/projects/{project_uuid}/`:

| Method                  | Path                           | Purpose                                                                                                                                                                 |
| ----------------------- | ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET                     | `overview/`                    | Progress, links, newest 10 updates + `updates_total`, milestone summaries — one request                                                                                 |
| GET                     | `progress/`                    | Work-item counts by state group; `cancelled` is out of scope, not outstanding, so it leaves the denominator                                                             |
| GET                     | `activity/`                    | `IssueActivity` for the project, cursor-paginated 20 at a time                                                                                                          |
| GET/POST · PATCH/DELETE | `updates/` · `updates/{uuid}/` | The noticeboard. `?entity_name=work_item&entity_identifier=` targets an item; `?parent=` fetches replies; `?label=` filters by topic. PATCH/DELETE need author or ADMIN |
| GET                     | `frontline/`                   | Intake grouped by the project's chosen dimension. `dimension: null` when none is marked — the signal to render nothing                                                  |
| GET                     | `attention/`                   | Overdue before urgent, oldest miss first, ≤5, with `total_overdue`/`total_urgent` saying what the cap held back                                                         |
| GET/POST · PATCH/DELETE | `milestones/`, `links/`        | Also on `/api/v1` (milestones under `portfolio`, links per work item)                                                                                                   |

### What an agent can still do

Not reaching the panels does not mean not feeding them. Everything they read from is on `/api/v1`:

| To make this appear                 | Write this over `/api/v1`                                                                              |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------ |
| A row in the frontline panel        | `intake-issues/` for the report, then `work-items/{uuid}/properties/{property_uuid}/` to attribute it  |
| A new frontline grouping            | `work-item-properties/` with a `select`/`multi_select` — a human marks it as the dimension in settings |
| An item in the attention panel      | a `work-items/` `target_date` in the past, or `priority: urgent`, in a live state                      |
| A noticeboard topic                 | `labels/` — the panel renders whatever the project has                                                 |
| Movement in progress / release gate | state transitions and test results, as usual                                                           |

The one thing an agent cannot do is post to the noticeboard — `updates/` has no `/api/v1` route at all. Treat that as a property to preserve rather than a gap to close: an announcement is a person telling other people something, and a board that fills itself with generated status is the failure mode this surface was built to replace.

### The grouping dimension

`frontline/` groups by whichever `WorkItemProperty` carries `is_grouping_dimension` — at most one per project, `select` or `multi_select` only. No category name exists in the API: the panel's heading is the property's name, and its rows are the option labels, so one project groups by customer and the next by region without a code change. Read it from `work-item-properties/`; a multi-select value puts one report under several headings, and reports with no value are returned as a `value: null` group rather than dropped.

Intake statuses fold into three answers: pending/snoozed → `pending`, accepted → `accepted`, rejected/duplicate → `declined`. Retriage is `PATCH intake-issues/{issue_uuid}/` with `{"status": 1}`, on either tree — **keyed by the work item's id, not the intake row's**, and ADMIN only. Passing the intake row id returns a 404 that reads like a permissions problem. Status values: `-2` pending, `0` snoozed, `1` accepted, `-1` rejected, `2` duplicate.

## Automation ingestion

```
POST .../testing/automation-ingestions/
X-API-Key: <token>            (public tree)
Idempotency-Key: <stable key>  ← required, 400 if missing
```

JUnit body: `{"format":"junit", "source":"github-actions", "name":"main / test / 421", "build":"<git-sha>", "configuration":{...}, "artifact_ids":["<FileAsset uuid>"], "junit_xml":"<testsuite>..."}`.
Generic body: `{"format":"results", "source":"playwright", "name":"...", "results":[{"external_id":"suite/test-id", "title":"...", "status":"passed", "duration_ms":812, "actual_result":{}, "test_case_id":"<uuid, optional>"}]}`.

Semantics:

- Idempotency: canonical payload sha256 vs stored hash. New → **201**; identical replay → **200** with `replayed:true`; same key + different payload → **409** `IdempotencyConflict`. Key recipe: `{repository}:{workflow_run_id}:{job}:{attempt}`.
- Case mapping order: existing `TestCaseAutomationLink(source, external_id)` → supplied `test_case_id` → **auto-create** a case tagged `["automated"]` (+ link), reported in `diagnostics` as `test_case_created`.
- Each upload creates one fixed run and one result per mapped case; `diagnostics` also reports `invalid_result`, `duplicate_external_id`, `artifact_unavailable`.
- JUnit parser: ≤5 MiB; rejects `<!DOCTYPE`/`<!ENTITY` (XXE); failure/error→`failed`, skipped→`skipped`, else `passed`; `external_id = "classname::name"`.
- Response: `{id, idempotency_key, replayed, test_run:{id,name,status,passed,failed,blocked,skipped,open}, diagnostics}`.
- `artifact_ids` are re-tagged asynchronously (Celery) as testing artifacts; result rows are authoritative regardless of task completion.

## Error contract (public tree)

Every ≥400 response uses a stable envelope and echoes `X-Request-ID` (send your own or one is generated):

```json
{"error": {"code": "http_409", "message": "Only an empty test folder can be deleted.", "details": {...}, "request_id": "<uuid>"}}
```

## Release gate

`overview.release_gate.ready` = a latest run exists AND zero blockers, where blockers = failed/blocked/open cases in the latest run + open defects. A defect is "open" while its issue's state **group** is anything other than `completed` or `cancelled` (state groups come from `states/`). Report blockers, coverage, failures, and open defects together — never infer readiness from one number.

## Which work items owe a contract

`requirement-coverage/` does not return one row per work item, and reading it as if it did makes
both the numerator and the denominator wrong. Four rules decide, all in
`plane/app/views/testing/report.py`:

1. **Only types with `needs_acceptance` produce a row.** An implementation task is how something
   gets built, not something the product promises; the story above it carries the promise. The
   shipped default is `true` for Epic/Feature/Story and `false` for Task/Bug. Their linked cases
   still roll up — the walk down the hierarchy does not care whether a child earns a row of its own.
2. **Work items with no type at all are kept.** A project that never adopted types would otherwise
   report nothing, and silence is the one answer a coverage report must not give.
3. **`backlog` and `cancelled` state groups are out of scope.** Nobody has scheduled the first and
   the second will never ship. Definition of Ready asks for the contract when work is scheduled, so
   the first state that owes one is whatever `unstarted` state the project schedules into.
4. **A row that summarises other counted rows does not count toward the totals.** An epic is
   covered exactly when its stories are; counting it again is a second vote for one decision. It
   still gets a row, and its own directly-linked contracts still count.

Defects are excluded before any of this. That is a separate rule from #1, and both are needed: the
type says what a row is _for_, the link says where it _came from_, and a defect filed under some
other type is evidence rather than a promise.

`needs_acceptance` is a workspace-level field on the type
(`PATCH /workspaces/{slug}/work-item-types/{uuid}/`, both trees). Flipping it changes what every
project in the workspace counts, so treat it as a configuration decision, not a way to move a
number.

## Requirement nature (`requirement_kind`)

`Issue.requirement_kind` carries whether a requirement is functional or a quality constraint:
`functional` | `quality` | `none`, defaulting to `none`.

Unusually, the public tree is the _only_ way in. `/api/v1` `work-items/` reads and writes it like
any other field, while the app tree's serializer omits it from its field list — so the web UI can
neither show nor set it, and neither the CLI nor MCP has a dedicated flag. Outside the seed and
`converge_work_item_types`, an API-key caller is the only thing that sets it:

```bash
curl -X PATCH "$BASE/work-items/<issue_uuid>/" -H "X-API-Key: $PLANE_API_KEY" \
  -H "Content-Type: application/json" -d '{"requirement_kind": "quality"}'
# CLI equivalent: plane-qa issue update --issue QA-12 --body '{"requirement_kind":"quality"}'
```

Two things follow, and both are mistakes this field exists to prevent:

- **Do not create a work-item type for it.** Type already carries breadth through `level`; adding
  nature multiplies the two axes, and one workspace here reached nine types that way before
  `converge_work_item_types` collapsed them back.
- **Do not create a custom property for it.** A property is defined per project, so every new
  project would have to declare it before the question could be asked at all, and no report
  spanning projects could ask it.

`none` is not `null`: a Task implements a requirement and a Bug reports a broken one, so neither
_is_ one. `null` would read as "not yet classified", which is a different claim. Nothing in the
coverage report reads this field today — `needs_acceptance` decides who owes a contract. It answers
_what kind of promise this is_, not _whether one is owed_.
