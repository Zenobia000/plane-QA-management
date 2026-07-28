# Plane QA Agent Tooling Architecture

Status: accepted for implementation

## Purpose

Expose the integrated Plane project-management and QA product to humans, CI, Codex, Claude Code, and other MCP
clients without duplicating business rules or granting database access.

## Component model

```mermaid
flowchart LR
    Humans[Humans and CI] --> CLI[plane-qa CLI]
    Agents[Codex / Claude Code] --> MCP[plane-qa-mcp]
    CLI --> SDK[@plane/qa-sdk]
    MCP --> SDK
    SDK --> API[Plane QA REST API]
    API --> PM[Project / Work Item services]
    API --> QA[Testing services]
    API --> Reports[Quality reporting]
    PM --> DB[(PostgreSQL)]
    QA --> DB
    Reports --> DB
    QA --> Queue[Celery / RabbitMQ]
    Queue --> Assets[(MinIO)]
```

The REST API is authoritative. The SDK owns transport and identifier resolution. CLI owns terminal interaction. MCP
owns typed agent tools and policy metadata. Neither client layer imports Django code or connects to storage.

## Trust boundaries

1. `X-API-Key` authenticates REST calls. Tokens remain in environment variables or an OS credential store.
2. Django permissions enforce workspace and project membership on every request; client-side checks are advisory only.
3. STDIO MCP is the initial local transport. It inherits only explicitly forwarded `PLANE_URL` and `PLANE_API_KEY`.
4. Remote Streamable HTTP MCP is feature-gated until the deployment has HTTPS, per-user OAuth, token rotation, and
   server-side audit identity. The current LAN HTTP origin is not an internet-facing MCP endpoint.
5. Tool results and errors never echo credentials or raw authorization headers.

## Domain modules inside one MCP server

| Module               | Responsibility                                                   | Representative tools                                                                               |
| -------------------- | ---------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Discovery            | Resolve workspace/project context and available capabilities     | `project_list`, `project_get_context`, `project_state_list`                                        |
| Project management   | Work item lifecycle and comments                                 | `issue_list`, `issue_get`, `issue_create`, `issue_update`, `issue_transition`, `issue_add_comment` |
| QA library           | Folders, immutable case versions, attachments, requirement links | `test_folder_*`, `test_case_*`, `test_case_attachment_*`, `testing_search`, `testing_export`       |
| QA execution         | Fixed runs, append-only results, traceable defects               | `test_run_*`, `test_result_record`, `test_result_create_defect`                                    |
| Quality intelligence | Overview, coverage, blockers, release decision                   | `quality_overview`, `quality_coverage`, `quality_release_gate`                                     |
| Automation           | Idempotent CI result ingestion                                   | `automation_upload_junit`, `automation_upload_results`                                             |

One external MCP server is intentional: project and QA operations share identity, project context, permissions, issue
states, traceability, and audit history. Internal modules remain independent and communicate only through the SDK.

## CLI taxonomy

```text
plane-qa project list|get|update|states
plane-qa issue list|get|create|update|transition|comment|archive
plane-qa folder list|get|create|update|delete
plane-qa case list|get|create|update|version|archive|link-issue|unlink-issue|attachments|attach|detach
plane-qa search query --query QUERY [--scope all|test_cases|work_items]
plane-qa export testing --format csv|html|excel --output FILE
plane-qa run list|get|create|record-result|create-defect|close
plane-qa quality overview|coverage|release-gate
plane-qa automation upload-junit|upload-results
```

Every command supports JSON output. Normal data goes to stdout; diagnostics go to stderr. Exit codes are stable:

| Code | Meaning                                  |
| ---: | ---------------------------------------- |
|    0 | Success                                  |
|    2 | Invalid command or local input           |
|    3 | Authentication failure                   |
|    4 | Permission denied                        |
|    5 | Resource not found                       |
|    6 | Conflict, including idempotency conflict |
|    7 | Destructive confirmation required        |
|    8 | Network, timeout, or retry exhaustion    |
|    1 | Unclassified failure                     |

## Safety policy

### Read-only

Discovery, list, get, overview, coverage, and release-gate operations may run without an additional confirmation.

### Writes

Create, update, transition, comment, link, result, defect, and close operations are explicitly marked as writes. MCP
clients should use their write-tool approval mode. Every retryable create accepts or derives a stable idempotency key.

### Destructive operations

Archive and delete commands require `--yes` in non-interactive CLI usage. Interactive CLI may ask for confirmation.
MCP does not expose permanent deletion of test cases or work items. Cases are archived, attachments are soft-deleted,
and folder deletion is allowed only for an empty folder. Each destructive tool requires an explicit literal confirmation.

### Immutable execution history

- Updating a case publishes a new version.
- Creating a run pins current case versions.
- Recording a result appends a new sequence.
- Results cannot be updated or deleted.
- Closed runs reject new results.
- A defect is created through the Testing domain so the result-to-work-item link is atomic.

## MCP result contract

Tools return structured content with a concise text summary and bounded JSON data. List tools require pagination and
never return an unbounded workspace dump. Errors contain a stable category, safe message, HTTP status when applicable,
and retryability; they never include a token.

Tool annotations follow intent:

| Tool kind              | `readOnlyHint` | `destructiveHint` |                            `idempotentHint` |
| ---------------------- | -------------: | ----------------: | ------------------------------------------: |
| list/get/report        |           true |             false |                                        true |
| create                 |          false |             false | false unless an idempotency key is supplied |
| update/transition/link |          false |             false |                          operation-specific |
| close/archive/delete   |          false |              true |                          operation-specific |

## Compatibility and versioning

- REST additions remain under `/api/v1`.
- SDK, CLI, and MCP share one repository version and are tested against the same API contracts.
- Additive fields are non-breaking. Removing/renaming commands, tools, fields, or status values requires a major
  tooling version and a migration note.
- MCP tool names and input schemas are public contracts even when the server is only local.

## Verification strategy

1. Django/PostgreSQL contract tests prove auth, membership, cross-project isolation, versioning, append-only execution,
   and idempotency.
2. SDK unit tests use a real HTTP test server or deterministic fetch doubles for headers, retries, timeouts, errors,
   and payloads.
3. CLI tests execute the built binary and assert stdout, stderr, exit codes, redaction, and confirmation behavior.
4. MCP tests use an MCP client over STDIO to initialize, list tools, validate schemas, and invoke read/write calls.
5. A disposable localhost journey exercises one project and proves equivalent CLI and MCP outcomes.
