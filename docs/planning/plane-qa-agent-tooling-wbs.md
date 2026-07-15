# Plane QA Agent Tooling — Development WBS

Baseline: `plane-QA-management` on `agent/testing-platform`

Delivery target: one integrated Plane QA REST contract, TypeScript SDK, CLI, MCP server, and Agent Skill in this
monorepo.

## Status legend

- `TODO`: not started
- `DOING`: actively being implemented
- `DONE`: implementation and listed verification evidence both exist
- `BLOCKED`: cannot proceed without an external decision or dependency

## Architectural invariants

1. REST APIs remain the business-system boundary; CLI and MCP never access PostgreSQL directly.
2. CLI and MCP share one typed SDK and must not implement divergent payload mappings.
3. One MCP server exposes project-management, QA, reporting, and automation tool groups.
4. Test case changes publish immutable versions; run membership pins a version.
5. Test results are append-only and closed runs cannot be mutated.
6. Destructive operations require explicit confirmation and are never hidden inside generic update tools.
7. API tokens, MCP credentials, and local `.env` files are never committed.
8. Every write is permission-checked, attributable to an actor, and returns machine-readable JSON.

## WBS

| ID   | Work package                   | Depends on   | Deliverable                                                                                                             | Verification                     | Status |
| ---- | ------------------------------ | ------------ | ----------------------------------------------------------------------------------------------------------------------- | -------------------------------- | ------ |
| 0.1  | Current-state inventory        | —            | Existing Project, Work Item, State, Testing, auth, package, and test surfaces mapped                                    | Source audit                     | DONE   |
| 0.2  | Architecture contract          | 0.1          | Component, trust-boundary, transport, and domain-module design                                                          | Document review                  | DONE   |
| 0.3  | Command and tool taxonomy      | 0.1          | Stable CLI commands and MCP tool names grouped by domain                                                                | Contract review                  | DONE   |
| 0.4  | Safety policy                  | 0.1          | Read/write/destructive classification, confirmation, idempotency, and audit rules                                       | Policy tests                     | DONE   |
| 0.5  | Completion matrix              | 0.2–0.4      | Requirement-to-test and evidence mapping                                                                                | WBS audit                        | TODO   |
| 1.1  | API-key Testing base           | 0.2          | Shared API-key authentication, throttling, and project permission behavior                                              | Auth contracts                   | DONE   |
| 1.2  | Capability and discovery API   | 1.1          | Project Testing capabilities and project context readable by agents                                                     | API contracts                    | DONE   |
| 1.3  | Quality reporting API          | 1.1          | Overview, requirement coverage, and release gate available through `/api/v1`                                            | API contracts                    | DONE   |
| 1.4  | Folder API                     | 1.1          | List, create, get, update, and delete-empty/archive-safe behavior                                                       | CRUD contracts                   | DONE   |
| 1.5  | Test case API                  | 1.1          | List, create, get, version-publishing update, archive, and version read                                                 | CRUD/version contracts           | DONE   |
| 1.6  | Case–work-item links           | 1.5          | List, create, and unlink same-project traceability                                                                      | Isolation contracts              | DONE   |
| 1.7  | Test run API                   | 1.1, 1.5     | List, create fixed run, get, record result, create defect, and close                                                    | Lifecycle contracts              | DONE   |
| 1.8  | Automation ingestion API       | 1.1          | Existing JUnit/generic ingestion preserved with retry idempotency                                                       | Ingestion contracts              | DONE   |
| 1.9  | Public API error contract      | 1.2–1.8      | Stable error code, message, details, and correlation identifier                                                         | Negative contracts               | TODO   |
| 1.10 | API documentation              | 1.2–1.9      | Endpoint, payload, examples, immutability, and permission reference                                                     | Docs verification                | TODO   |
| 2.1  | SDK package scaffold           | 0.2          | `@plane/qa-sdk` workspace package with strict TypeScript build                                                          | Typecheck/build                  | TODO   |
| 2.2  | HTTP transport                 | 2.1          | Base URL, `X-API-Key`, timeout, retry, rate-limit, and error decoding                                                   | Unit tests                       | TODO   |
| 2.3  | Context resolution             | 2.2          | Workspace slug, project identifier/UUID, issue identifier, and case sequence resolution                                 | Unit/live contracts              | TODO   |
| 2.4  | Project-management client      | 2.2          | Projects, states, work items, and comments API client                                                                   | Unit/contracts                   | TODO   |
| 2.5  | Testing client                 | 2.2          | Capabilities, folders, cases, links, runs, results, defects, and reports client                                         | Unit/contracts                   | TODO   |
| 2.6  | Automation client              | 2.2          | JUnit and generic result ingestion with idempotency                                                                     | Unit/contracts                   | TODO   |
| 2.7  | Stable exported schemas        | 2.3–2.6      | Public request/response types and runtime validation                                                                    | Type/schema tests                | TODO   |
| 3.1  | CLI package scaffold           | 2.1          | `plane-qa` executable, help, version, and completion-ready command registry                                             | CLI smoke                        | TODO   |
| 3.2  | CLI configuration/auth         | 2.2          | Environment/config resolution without exposing secrets                                                                  | Credential tests                 | TODO   |
| 3.3  | Machine output contract        | 3.1          | JSON stdout, human stderr, stable exit codes, and no ANSI in JSON mode                                                  | Snapshot tests                   | TODO   |
| 3.4  | Project commands               | 2.4, 3.3     | Project list/get/update and state list                                                                                  | CLI contracts                    | TODO   |
| 3.5  | Issue commands                 | 2.4, 3.3     | Work item list/get/create/update/transition/comment/archive                                                             | CLI contracts                    | TODO   |
| 3.6  | Folder and case commands       | 2.5, 3.3     | Folder CRUD, case CRUD/version read, link, and unlink                                                                   | CLI contracts                    | TODO   |
| 3.7  | Run and result commands        | 2.5, 3.3     | Run list/get/create/record-result/create-defect/close                                                                   | CLI contracts                    | TODO   |
| 3.8  | Quality commands               | 2.5, 3.3     | Overview, coverage, release gate, and open defects                                                                      | CLI contracts                    | TODO   |
| 3.9  | Automation commands            | 2.6, 3.3     | JUnit and generic upload with stable idempotency key                                                                    | CLI/live contracts               | TODO   |
| 3.10 | Destructive safeguards         | 0.4, 3.4–3.9 | `--dry-run`, `--yes`, TTY confirmation, and non-interactive refusal                                                     | Safety tests                     | TODO   |
| 4.1  | MCP package scaffold           | 2.1          | One `plane-qa-mcp` STDIO server using official MCP SDK                                                                  | Protocol smoke                   | TODO   |
| 4.2  | Server instructions            | 0.4, 4.1     | Cross-tool workflow, scope, append-only, and approval guidance                                                          | Initialization test              | TODO   |
| 4.3  | Discovery tools                | 2.3, 4.1     | Context, capabilities, projects, and states tools                                                                       | MCP tests                        | TODO   |
| 4.4  | Project-management tools       | 2.4, 4.1     | Typed project, work-item, transition, and comment tools                                                                 | MCP tests                        | TODO   |
| 4.5  | QA library tools               | 2.5, 4.1     | Typed folder, case, version, link, and unlink tools                                                                     | MCP tests                        | TODO   |
| 4.6  | QA execution tools             | 2.5, 4.1     | Typed run, result, defect, and close tools                                                                              | MCP tests                        | TODO   |
| 4.7  | Quality/reporting tools        | 2.5, 4.1     | Overview, coverage, release gate, and defect tools                                                                      | MCP tests                        | TODO   |
| 4.8  | Automation tools               | 2.6, 4.1     | JUnit/generic ingestion tools with idempotency                                                                          | MCP tests                        | TODO   |
| 4.9  | Tool annotations and approvals | 0.4, 4.3–4.8 | Read-only, idempotent, open-world, and destructive hints plus deny-by-default deletes                                   | Schema/policy tests              | TODO   |
| 4.10 | Output bounding                | 4.3–4.8      | Pagination, concise summaries, structured content, and token-safe errors                                                | Load tests                       | TODO   |
| 4.11 | Remote transport design        | 4.1          | Streamable HTTP/OAuth deployment contract; implementation remains feature-gated until HTTPS exists                      | Design/security review           | TODO   |
| 5.1  | Agent Skill scaffold           | 3.1, 4.1     | `.agents/skills/plane-qa` initialized with required metadata                                                            | `quick_validate.py`              | TODO   |
| 5.2  | Agent workflows                | 4.3–4.8      | Issue lifecycle, failed-test defect, retest, release-gate, and CI triage procedures                                     | Scenario tests                   | TODO   |
| 5.3  | Safety guidance                | 0.4, 5.2     | Confirmation, scope, secrets, prompt-injection, and immutable-history rules                                             | Skill review                     | TODO   |
| 5.4  | Tool reference                 | 4.3–4.9      | Progressive-disclosure MCP/CLI reference consumed only when needed                                                      | Skill scenario                   | TODO   |
| 5.5  | Codex configuration            | 4.1          | Project-scoped STDIO config/example without credentials                                                                 | Codex MCP smoke                  | TODO   |
| 5.6  | Claude Code configuration      | 4.1          | Project MCP config/example without credentials                                                                          | Claude MCP schema smoke          | TODO   |
| 6.1  | SDK unit suite                 | 2.2–2.7      | Transport, validation, retry, error, and identifier cases                                                               | Vitest                           | TODO   |
| 6.2  | CLI unit suite                 | 3.1–3.10     | Command parsing, JSON, exits, confirmations, and redaction                                                              | Vitest                           | TODO   |
| 6.3  | MCP protocol suite             | 4.1–4.10     | Initialize, list-tools, valid calls, invalid input, permission, and bounded output                                      | MCP client tests                 | TODO   |
| 6.4  | Backend affected suite         | 1.1–1.10     | All Testing and existing public API contracts remain green                                                              | Pytest/PostgreSQL                | TODO   |
| 6.5  | Live localhost journey         | 1–5          | Agent reads overview, creates/updates issue and case, links, runs, records failure, creates defect, retests, and closes | Destructive local E2E            | TODO   |
| 6.6  | CI ingestion retry             | 3.9, 4.8     | Same logical upload produces one ingestion/run/result set                                                               | Live idempotency check           | TODO   |
| 6.7  | Security isolation             | 1–5          | Anonymous, invalid token, non-member, cross-project, injection, and secret-redaction cases                              | Negative suite                   | TODO   |
| 6.8  | Build/package gates            | 2–5          | Typecheck, lint, format, package builds, executable smoke, and clean diff                                               | Monorepo gates                   | TODO   |
| 7.1  | Local deployment wiring        | 3–4          | CLI/MCP build targets and optional container/profile without changing default Web startup                               | Compose smoke                    | TODO   |
| 7.2  | Operator documentation         | 1–7          | Install, configure, rotate token, invoke from Codex/Claude, troubleshoot, and upgrade                                   | Runbook review                   | TODO   |
| 7.3  | Versioning contract            | 2–5          | API/SDK/CLI/MCP compatibility and release policy                                                                        | Release review                   | TODO   |
| 7.4  | Final completion audit         | all          | Every WBS row has authoritative implementation and verification evidence                                                | Requirement-by-requirement audit | TODO   |

## Release-blocking acceptance journeys

1. An API-key principal can discover a project, list states, create a work item, transition it, comment, and read it back.
2. The same principal can create a test case, publish a new version, link it to that work item, and prove a pre-existing
   fixed run still references the old version.
3. An agent can create a run, record a failed result, create a traceable defect, resolve it, observe ready-for-retest,
   record a pass, and close the run without mutating history.
4. CLI and MCP produce equivalent structured results for the same read and write operations through the shared SDK.
5. A repeated automation upload with one idempotency key creates exactly one ingestion, run, and result set.
6. Invalid tokens, non-members, cross-project identifiers, malformed input, and unconfirmed destructive operations are
   rejected without partial writes.
7. Codex and Claude Code can both initialize the same STDIO MCP server, discover typed tools, and complete a read/write
   scenario without receiving a raw API token in model-visible output.

## Completion evidence

| Evidence                 | Result                                                                                                                                                                                 |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Backend API contracts    | `10 passed`: public auth, management lifecycle, immutable versions, append-only results, errors, hierarchy cycles, idempotency, non-member, invalid token, and cross-project isolation |
| SDK suite                | `7 passed`: auth header/redaction, retry, errors, project/issue resolution, runtime schema rejection, and idempotency                                                                  |
| CLI suite                | `7 passed`: help, JSON contract, exit/redaction, refusal, `--yes`, TTY confirmation, and `--dry-run`                                                                                   |
| MCP protocol suite       | `5 passed`: tool discovery/annotations, structured calls, confirmation rejection, safe errors, and bounded output                                                                      |
| Package gates            | SDK, CLI, and MCP typecheck, lint, format, test, and build passed; built CLI help smoke passed                                                                                         |
| Live localhost lifecycle | Real API at `http://127.0.0.1:8787`: issue + case link, pinned case v1, published v2, failed result, defect, passed retest, close; E2E data removed                                    |
| Live automation retry    | Same idempotency key returned the same ingestion; first `replayed=false`, second `replayed=true`; fixture data removed                                                                 |
| Live MCP                 | Built STDIO server initialized, exposed 35 integrated tools, and resolved real project context                                                                                         |
| Agent clients            | Codex accepted STDIO/env/approval config fields; Claude Code discovered the tracked server as project-scoped pending approval; both config files contain no secret value               |
| Agent Skill              | `quick_validate.py` returned `Skill is valid!`                                                                                                                                         |
