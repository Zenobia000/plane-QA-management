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
| GET              | `requirement-coverage/`                               | Per-work-item coverage; multiple linked cases roll up worst-wins: `failed < blocked < open < skipped < passed`                                                                                                                                                                                                  |
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
| GET/POST                    | `work-items/`, `labels/`, `states/`, `members/`              | Work items (fields incl. `start_date` ≤ `target_date`, `assignees` must be project members, `labels`), plus supporting lookups                                                    |
| GET/POST · GET/PATCH/DELETE | `views/` · `views/{uuid}/`                                   | Saved views. Send `filters`; `query` is compiled from it server-side and a supplied one is ignored. PATCH on a locked view returns 409; DELETE requires ownership (403 otherwise) |

### Workspace-scoped views

Relative to `/api/v1/workspaces/{slug}/` — the same handlers with no project segment:

| Method                      | Path                       | Purpose                                                                        |
| --------------------------- | -------------------------- | ------------------------------------------------------------------------------ |
| GET/POST · GET/PATCH/DELETE | `views/` · `views/{uuid}/` | Views spanning every project in the workspace; responses carry `project: null` |

Visibility for both scopes is the model's own rule, not the browser's: your views plus every `access: 1` (public) one. `access: 0` is private to its owner, and a key acts for its user.

Pages have no public endpoints. Their content is a Yjs CRDT document, so an HTML-only write is safe only for a page that has never been opened; that is out of scope here.

## CE work-item extensions

These are native to this fork's `/api/v1/` tree; do not call Plane commercial endpoints for them.

| Method                      | Path                                                                                          | Scope and purpose                                                                                      |
| --------------------------- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ------ | ---- | ------- | ------ | ------------ | ------------------------------------------- |
| GET/POST · GET/PATCH/DELETE | `/workspaces/{slug}/work-item-types/` · `.../work-item-types/{type_uuid}/`                    | Workspace type definitions. POST/PATCH/DELETE requires an active workspace Admin or Member.            |
| GET/POST · GET/PATCH/DELETE | `/workspaces/{slug}/projects/{project_uuid}/work-item-types/` · `.../{project_type_uuid}/`    | Enable/order/default a workspace type in one project. A Work Item may use only an enabled active type. |
| GET/POST · GET/PATCH/DELETE | `/workspaces/{slug}/projects/{project_uuid}/work-item-properties/` · `.../{property_uuid}/`   | Project custom-property definitions. `kind` is `text                                                   | number | date | boolean | select | multi_select | url`; options require unique stable values. |
| GET · PUT/DELETE            | `.../work-items/{issue_uuid}/properties/` · `.../properties/{property_uuid}/`                 | Read, set, or clear a typed custom value. Property and work item must be in the same project.          |
| GET/POST · GET/PATCH/DELETE | `/workspaces/{slug}/projects/{project_uuid}/milestones/` · `.../milestones/{milestone_uuid}/` | Project delivery checkpoints. A Work Item `milestone` must be from its own project.                    |
| GET/POST · GET/PATCH/DELETE | `/workspaces/{slug}/initiatives/` · `.../initiatives/{initiative_uuid}/`                      | Workspace strategic outcomes, with optional same-workspace `project_ids`.                              |

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
