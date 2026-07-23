# Plane QA — codebase map (for modifying the platform)

Layering rule: business logic lives only in `apps/api/plane/testing/` (framework-agnostic, `@transaction.atomic`, locks Project via `select_for_update`). Views are thin adapters; the public API subclasses the app views adding only auth/throttle/error-envelope. Never duplicate logic into a view, and never let SDK/CLI/MCP import Django code or touch the DB.

## Backend (Django, `apps/api/`)

| Layer                                                                     | Location                                                     |
| ------------------------------------------------------------------------- | ------------------------------------------------------------ |
| Models (all invariants in `save()`/`clean()`)                             | `plane/db/models/testing.py`                                 |
| Services (cases, versions, runs, results, defects, close)                 | `plane/testing/services.py`                                  |
| CI ingestion + JUnit parser + idempotency                                 | `plane/testing/automation.py`                                |
| CSV import/export                                                         | `plane/testing/portability.py`                               |
| App views (session auth)                                                  | `plane/app/views/testing/{capability,library,run,report}.py` |
| App URLs                                                                  | `plane/app/urls/testing.py`                                  |
| Public views (X-API-Key; thin subclasses + error envelope + X-Request-ID) | `plane/api/views/testing.py`                                 |
| Public URLs                                                               | `plane/api/urls/testing.py`                                  |
| Ingestion serializers                                                     | `plane/api/serializers/testing.py`                           |
| Celery artifact task (autoretry ×3)                                       | `plane/bgtasks/testing_artifact_task.py`                     |

Tests (canonical usage examples — read these before changing behavior):

- `plane/tests/contract/api/test_testing_management.py` — full API-key lifecycle: folder → case → version bump → link → run → fail → defect → retest → close → reports; plus 403/400/409 rejection paths.
- `plane/tests/contract/api/test_testing_automation.py` — idempotency replay/conflict, shared app+public idempotency store.
- `plane/tests/contract/app/test_testing_{capability,library,runs}.py`, `plane/tests/unit/testing/`, `plane/tests/unit/models/test_testing_library.py`.

## TypeScript tooling

| Package             | Location                 | Key files                                                                                                                             |
| ------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| SDK `@plane/qa-sdk` | `packages/qa-sdk/src/`   | `client.ts` (PlaneQAClient, retry, resolvers), `errors.ts`, `schemas.ts` (zod), `types.ts`                                            |
| CLI `@plane/qa-cli` | `apps/plane-qa-cli/src/` | `commands.ts` (dispatch), `run.ts` (exit codes, confirmation), `arguments.ts`, `config.ts`, `help.ts`                                 |
| MCP `@plane/qa-mcp` | `apps/plane-qa-mcp/src/` | `create-server.ts` (all 35 tool registrations + annotations), `server.ts` (stdio launcher), `results.ts` (truncation, error wrapping) |

Each has vitest specs beside the source (`client.spec.ts`, `run.spec.ts`, `create-server.spec.ts`). Check: `pnpm check:qa-tools`. SDK/CLI/MCP tool names and input schemas are public contracts — removals/renames need a major version + migration note.

## Web UI (`apps/web`)

| Piece                                                                                        | Location                                                                               |
| -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Testing tab route (Overview / Test cases / Test runs)                                        | `apps/web/app/(all)/[workspaceSlug]/(projects)/projects/(detail)/[projectId]/testing/` |
| Components (overview, library, run builder, execution workspace)                             | `apps/web/core/components/testing/`                                                    |
| MobX store                                                                                   | `apps/web/core/store/testing.store.ts`                                                 |
| HTTP service (app tree, `/api/...` — session auth, by design different from SDK's `/api/v1`) | `packages/services/src/testing/testing.service.ts`                                     |
| Issue-detail "Testing coverage" panel                                                        | `apps/web/core/components/issues/issue-detail/testing-summary.tsx`                     |

## Docs & decisions

- `docs/architecture/testing-platform-workflow.md` — architecture contract, C4, invariants, delivery workflow.
- `docs/architecture/plane-qa-agent-tooling.md` — tooling architecture, safety policy, versioning.
- `docs/api/testing-management.md`, `docs/api/testing-automation.md` — API contracts.
- `docs/architecture/decisions/0001..0004` — ADRs (case aggregate/versioning, immutable execution, automation ingestion, milestones/fork boundaries).
- `docs/operations/plane-qa-agent-tooling.md` — runbook, troubleshooting.
- `.agents/skills/plane-qa/` — cross-agent (Codex/OpenAI) policy skill for the same system.

## Invariants to preserve when changing code

1. `TestCaseVersion`, `TestStep`, `TestResult` raise on update — keep immutability in the model layer, not just views.
2. Every model's `clean()` enforces same-workspace/same-project across all FKs; new FKs must join that check.
3. Case edit = `publish_test_case_version` (new version + pointer bump) in one transaction.
4. Run creation pins versions; completed runs must keep rejecting results and membership changes.
5. Defect creation stays atomic (Issue + `TestResultIssueLink` in one transaction) and limited to failed/blocked.
6. Idempotency = unique `(project, idempotency_key)` + canonical payload hash; replay 200, mismatch 409.
7. Release status must never depend on Celery completion — transactional rows are authoritative.
8. Prefer extension seams over upstream edits; Testing keeps its own migration chain — never edit upstream migrations (see `docs/architecture/testing-platform-workflow.md` §10 for fork/rebase strategy).
