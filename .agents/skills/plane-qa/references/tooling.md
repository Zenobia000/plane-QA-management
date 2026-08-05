# Plane QA — SDK, CLI, MCP tooling

## Build & verify

```bash
pnpm install
pnpm build:qa-tools   # builds @plane/qa-sdk → @plane/qa-cli → @plane/qa-mcp
pnpm check:qa-tools   # types + vitest + build for all three
```

Env vars (process env or secret manager only — never tracked files):

| Var               | Used by     | Notes                                                                     |
| ----------------- | ----------- | ------------------------------------------------------------------------- |
| `PLANE_URL`       | SDK/CLI/MCP | Base URL of the Plane instance                                            |
| `PLANE_API_KEY`   | SDK/CLI/MCP | Sent only as `X-API-Key`; never echoed by tools                           |
| `PLANE_WORKSPACE` | CLI         | Workspace slug (CLI flag `--workspace`)                                   |
| `PLANE_PROJECT`   | CLI         | Project UUID or identifier; required for everything except `project list` |

## SDK — `@plane/qa-sdk` (`packages/qa-sdk/`)

```ts
import { PlaneQAClient, PlaneQAError } from "@plane/qa-sdk";
const client = new PlaneQAClient({ baseUrl, apiKey, timeoutMs: 15000, maxRetries: 3 });
```

- Retries network errors and 429/502/503/504 with exponential backoff (honors `Retry-After`) — but only for GET/HEAD/OPTIONS or calls marked idempotent (e.g. `ingestAutomation`).
- Errors throw `PlaneQAError { kind, status?, details?, retryable }`; `kind` ∈ `authentication(401) | permission(403) | not_found(404) | conflict(409) | rate_limit(429) | validation(other 4xx) | server(5xx) | network`.
- Reference resolvers: `resolveProject` (UUID or identifier), `resolveIssue` (UUID or `QA-123`), `resolveTestCase` (UUID or sequence number).

Method groups (all take `workspace` first, most then `projectId`):

| Group           | Methods                                                                                                                                                                                                                                                  |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Projects/states | `listProjects`, `getProject`, `updateProject`, `resolveProject`, `listStates`                                                                                                                                                                            |
| Work items      | `listIssues`, `getIssue`, `getIssueByIdentifier`, `resolveIssue`, `createIssue`, `updateIssue`, `archiveIssue`, `addIssueComment`                                                                                                                        |
| Extensions      | `listWorkItemTypes`, `createWorkItemType`, `enableWorkItemType`, `createProjectWorkItemType`, `listWorkItemProperties`, `createWorkItemProperty`, `setWorkItemPropertyValue`, `listMilestones`, `createMilestone`, `listInitiatives`, `createInitiative` |
| Views           | `listViews`, `getView`, `createView`, `updateView`, `deleteView` — each takes `projectId` last and **optional**; omit it for a workspace view                                                                                                            |
| Testing reads   | `getTestingCapabilities`, `getQualityOverview`, `getRequirementCoverage`                                                                                                                                                                                 |
| Folders         | `listFolders`, `getFolder`, `createFolder`, `updateFolder`, `deleteFolder`                                                                                                                                                                               |
| Cases           | `listTestCases`, `getTestCase`, `resolveTestCase`, `createTestCase`, `updateTestCase`, `archiveTestCase`, `getTestCaseVersion`, `listTestCaseLinks`, `linkTestCase`, `unlinkTestCase`                                                                    |
| Runs            | `listTestRuns`, `getTestRun`, `createTestRun`, `recordTestResult`, `createDefect`, `closeTestRun`                                                                                                                                                        |
| Automation      | `ingestAutomation(workspace, projectId, idempotencyKey, input)`                                                                                                                                                                                          |

## CLI — `plane-qa` (`apps/plane-qa-cli/`, bin `dist/cli.mjs`)

`node apps/plane-qa-cli/dist/cli.mjs <group> <action> [flags]`. Flags: `--flag value` or `--flag=value`; JSON flags parsed strictly. Success = pretty JSON on stdout; errors = `{error:{code,message}}` on stderr.

Escape hatch: `project update`, `initiative create`, `type create`, `property create`, `milestone create`, `issue create/update/transition`, `case create/update`, and `run create` all accept `--body <JSON>` whose keys are spread verbatim into the request payload — use it for fields without dedicated flags (issue `start_date`/`target_date`/`assignees`/`labels`/`type_id`/`parent`, type `needs_acceptance`, run `cycle_id`/`module_id`, …). Dedicated flags win only by position; keep a field in exactly one place.

`--requirement-kind none|functional|quality` (MCP: `requirement_kind`) says what a work item _states_: a behaviour the system must have (`functional`, an FR), how well it must behave (`quality`, an NFR), or nothing — `none` is what a task implementing a requirement and a bug reporting one broken both are. It is independent of the work item type, so any level of Epic → Feature → Story can carry any of the three; see the requirement-classification section of the delivery guideline for why nature is not another tier of type. Omitting the flag leaves the stored value alone, because `none` is a classification rather than an absence and a default would declassify every requirement touched by an unrelated rename.

`issue list` takes the same flag as a filter, comma-separated for a union — `--requirement-kind functional,quality` is every requirement regardless of nature, `--requirement-kind quality` is the NFRs at epic, feature and story level alike. Both API trees honour it. A kind the server does not recognise selects nothing rather than everything, so a misspelling comes back as an empty list; the CLI and the MCP schema both reject one before the request for that reason.

The browser shows and sets it too, so what an agent classifies here is what a person sees: a Requirement kind row in the work item's properties sidebar and in the peek view, and a control in the create/edit modal. What the UI does **not** yet have is a way to filter or group a board by it — that is API-only, via the flag above.

| Group        | Actions                                                                                                                                                                                                                                                                                                 |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | -------------------------------------------------- |
| `project`    | `list` (no `--project` needed) · `get` · `states` · `update --name --description`                                                                                                                                                                                                                       |
| `initiative` | `list` (no `--project` needed) · `create --name [--description --target-date --status --sort-order --project-ids uuid1,uuid2]`                                                                                                                                                                          |
| `type`       | `list` · `create --name [--description --is-epic --is-default --level --body '{"needs_acceptance":false}']` — creates the workspace type and enables it for the configured project                                                                                                                      |
| `property`   | `list` · `create --name --kind [--description --is-required --sort-order --default-value <JSON> --options <JSON>]` · `set --issue --property-id --value <JSON>`                                                                                                                                         |
| `milestone`  | `list` · `create --name [--description --target-date --status --sort-order]`                                                                                                                                                                                                                            |
| `issue`      | `list [--state --priority --requirement-kind --leaf-only --per-page]` · `create --name [--state-id --priority --description --requirement-kind --body <JSON>]` · `get --issue` · `update` / `transition --issue --state-id [--requirement-kind --body]` · `comment --issue --body` · `archive --issue`† |
| `folder`     | `list` · `create --name [--parent-id --sort-order]` · `get --folder` · `update --folder` · `delete --folder`†                                                                                                                                                                                           |
| `case`       | `list [--search --folder-id --issue-id --per-page]` · `create --title [...]` · `get/update/version/archive/link-issue/unlink-issue` · `attachments --case` · `attach --case --file --mime-type` · `detach --case --attachment`†                                                                         |
| `search`     | `query --query 'type:test_case priority:high payment' [--scope all                                                                                                                                                                                                                                      | test_cases | work_items]`                                       |
| `export`     | `testing --format csv                                                                                                                                                                                                                                                                                   | html       | excel --output FILE [--query QUERY --scope SCOPE]` |
| `run`        | `list` · `create --name --cases id1,id2 [--build --configuration <JSON> --body '{"cycle_id":"..."}']` · `get --run` · `record-result --run --run-case --status [--actual <JSON> --duration-ms]` · `create-defect --run --run-case --result [--name]` · `close --run`†                                   |
| `view`       | `list` · `create --name [--description --filters <JSON> --display_filters <JSON> --display_properties <JSON> --access 0\|1]` · `get --view` · `update --view [... --lock]` · `delete --view`† — add `--workspace_level` to address workspace views instead of the project's                             |
| `quality`    | `overview` · `release-gate` · `coverage` · `open-defects`                                                                                                                                                                                                                                               |
| `automation` | `upload-junit --idempotency-key K --file junit.xml --name "CI #42" [--source --build --configuration --artifact-ids]` · `upload-results --idempotency-key K --file results.json`                                                                                                                        |

† = destructive: requires `--yes`, interactive `yes`, or `--dry-run` (preview receipt, no write).

`upload-results --file` JSON shape (fixture: `apps/plane-qa-cli/src/fixtures/automation-results.json`):

```json
{
  "format": "results",
  "source": "playwright",
  "name": "browser regression",
  "build": "sha",
  "configuration": {},
  "results": [
    {
      "external_id": "checkout/visa",
      "title": "Visa checkout",
      "status": "passed",
      "duration_ms": 812,
      "actual_result": {}
    }
  ]
}
```

Exit codes: `0` ok · `1` server-side validation (HTTP 400, e.g. result on a completed run) · `2` usage/local input error · `3` auth · `4` permission · `5` not found · `6` conflict (incl. idempotency) · `7` confirmation refused · `8` network/rate-limit/server.

Note: `upload-results` takes only `--idempotency-key` and `--file` — `name`, `source`, `build`, `configuration` live inside the JSON file. `upload-junit` is the opposite: raw XML file + metadata flags.

## Saved views

A view is a stored work-item query plus how to display it. Two scopes, distinguished by whether a project is supplied: project views live inside one project, workspace views span every project in the workspace.

**Send `filters`; never send `query`.** The server compiles one from the other, and a supplied `query` is ignored rather than honoured — a view whose compiled filter disagreed with its stated filters would be wrong in a way nothing surfaces.

```jsonc
// filters — what you write
{ "state_group": ["started", "unstarted"], "priority": ["urgent", "high"] }
// query — what the server derives and stores
{ "state__group__in": ["started", "unstarted"], "priority__in": ["urgent", "high"] }
```

Common `filters` keys mirror work-item fields: `state`, `state_group`, `priority`, `assignees`, `labels`, `created_by`, `subscriber`, `start_date`, `target_date`, `module`, `cycle`.

`display_filters` controls presentation — `layout` (`list|kanban|calendar|spreadsheet|gantt_chart`), `group_by`, `order_by`, `sub_issue`, `show_empty_groups`. `display_properties` toggles per-card fields (`assignee`, `due_date`, `labels`, `estimate`, `key`, …). Both have server defaults, so send only what differs.

```bash
plane-qa view create --name "Scheduled without a contract" \
  --filters '{"state_group":["started","unstarted"],"priority":["urgent","high"]}' \
  --display_filters '{"layout":"spreadsheet","group_by":"state","order_by":"-priority"}'
```

Rules worth knowing before writing:

- `access` is `0` private or `1` public (default). A private view is visible only to the key's owner — a token acts for its user, so someone else's private view is not readable even within a shared project.
- `is_locked` blocks further updates with **409**, rather than silently discarding them. Unlock the same way you locked it.
- Deletion requires **ownership**, not project membership; deleting someone else's saved view returns 403.
- Pages are deliberately not exposed. Their content is a Yjs CRDT document, so writing HTML alone is safe only for a page nobody has opened — that is a separate problem from views, which are plain JSON.

## MCP server — `plane-qa-mcp` (`apps/plane-qa-mcp/`)

STDIO server: `node apps/plane-qa-mcp/dist/server.mjs`; needs `PLANE_URL` + `PLANE_API_KEY` (exits 2 if missing). Wired in `.mcp.json` (Claude Code) and `.codex/config.toml` (Codex, approval mode `writes`). All tools take `workspace` (+ `project` where scoped; accepts UUID or identifier).

| Domain     | Tools                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Context    | `project_list`, `project_get_context` (project + states + capabilities in one call — start here), `project_state_list`, `project_update`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| Extensions | `create_work_item_type` (creates + enables for `project`), `create_work_item_property`, `set_work_item_property_value`, `create_milestone`, `create_initiative` (workspace only; optional `project_ids`)                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| Work items | `issue_list` (`state?`, `priority?`, `leaf_only?` — pass `true` to see what the work-item list shows by default: items that summarise nothing. An epic or feature holding live children is excluded, since its state is hand-set and its estimate is blank; use the epic hierarchy for the summary view. `requirement_kind?` — comma-separated, e.g. `functional,quality`. Note `state?` and `priority?` are accepted but **not** honoured by this endpoint, which is a known gap), `issue_get`, `issue_create`, `issue_update` (both take `requirement_kind?`), `issue_transition` (issue + `state_id`), `issue_add_comment`, `issue_archive`‡ |
| Folders    | `test_folder_list`, `test_folder_create`, `test_folder_update`, `test_folder_delete`‡                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| Cases      | `test_case_list`, `test_case_get`, `test_case_create`, `test_case_update`, `test_case_version_get`, links/archive, `test_case_attachment_list`, `test_case_attachment_upload` (base64), `test_case_attachment_delete`‡                                                                                                                                                                                                                                                                                                                                                                                                                          |
| Search     | `testing_search` (controlled field DSL), `testing_export` (CSV/HTML UTF-8; XLSX returned base64)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| Runs       | `test_run_list`, `test_run_get`, `test_run_create` (`name`, `test_case_ids[]`, `build?`, `configuration?` — **no `cycle_id`/`module_id`**: for a sprint-scoped run use CLI `run create --body` or REST), `test_result_record` (`run_id`, `run_case_id`, `status`), `test_result_create_defect` (`run_id`, `run_case_id`, `result_id`), `test_run_close`‡                                                                                                                                                                                                                                                                                        |
| Views      | `view_list`, `view_get`, `view_create`, `view_update`, `view_delete`‡ — `project` is **optional here alone**: omit it to address workspace-level views spanning every project                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| Quality    | `quality_overview`, `quality_coverage`, `quality_release_gate`, `quality_open_defects`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| Automation | `automation_upload_junit` (`idempotency_key`, `name`, `junit_xml`), `automation_upload_results` (`idempotency_key`, `name`, `source`, `results[]` ≤10000)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |

‡ = destructive: requires `confirm: true` in the tool input. Note the CLI/MCP asymmetry: CLI `case unlink-issue` needs `--yes`, but MCP `test_case_unlink_issue` needs no confirm (it's a reversible idempotent write).

Priority enum: `urgent|high|medium|low|none`. Result status enum: `passed|failed|blocked|skipped`. Tool errors return `{isError:true}` with a stable `kind: message` and never leak the token.

For `create_work_item_property`, `kind` is one of `text|number|date|boolean|select|multi_select|url`. `select` and `multi_select` values must match an option's stable `value`, not its display label. `create_work_item_type`, custom-property definitions, milestones, and initiatives are writes but not destructive; all delete/archive/unlink rules above remain unchanged.

### One field MCP cannot reach

`IssueType.needs_acceptance` is a real field on the REST API with no tool input and no CLI flag of
its own. It decides whether items of that type produce a coverage row, and **a type created through
`create_work_item_type` defaults to `true`** — so a type meant for implementation work starts
demanding acceptance contracts, and every item of it reads as an uncovered requirement.

Set it with CLI `type create … --body '{"needs_acceptance":false}'`, or
`PATCH /api/v1/workspaces/{slug}/work-item-types/{uuid}/`. It is workspace-level: flipping it
changes what every project in the workspace counts, so treat it as a configuration decision rather
than a way to move a number.

Do not route around a missing input by inventing a property or a type to carry the value — that is
the failure mode `converge_work_item_types` exists to undo. `--body` and REST are the escape hatch.
