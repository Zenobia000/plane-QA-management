# Plane QA — codebase map (for modifying the platform)

The fork owns two halves. **Testing** is the QA domain below; **delivery** is everything this fork added to Plane's project management — work-item types and properties, milestones, initiatives, intake, automations, state transitions, templates, and the Project Overview. They share one project scope, and the split matters when deciding where code goes: testing has a service layer, delivery mostly does not.

Layering rule (testing): business logic lives only in `apps/api/plane/testing/` (framework-agnostic, `@transaction.atomic`, locks Project via `select_for_update`). Views are thin adapters; the public API subclasses the app views adding only auth/throttle/error-envelope. Never duplicate logic into a view, and never let SDK/CLI/MCP import Django code or touch the DB.

## Backend (Django, `apps/api/`)

| Layer                                                                     | Location                                                                    |
| ------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Models (all invariants in `save()`/`clean()`)                             | `plane/db/models/testing.py`                                                |
| Services (cases, versions, runs, results, defects, close)                 | `plane/testing/services.py`                                                 |
| CI ingestion + JUnit parser + idempotency                                 | `plane/testing/automation.py`                                               |
| CSV import/export                                                         | `plane/testing/portability.py`                                              |
| App views (session auth)                                                  | `plane/app/views/testing/{capability,library,run,report}.py`                |
| App URLs                                                                  | `plane/app/urls/testing.py`                                                 |
| Public views (X-API-Key; thin subclasses + error envelope + X-Request-ID) | `plane/api/views/testing.py`                                                |
| Public URLs                                                               | `plane/api/urls/testing.py`                                                 |
| Ingestion serializers                                                     | `plane/api/serializers/testing.py`                                          |
| Celery artifact task (autoretry ×3)                                       | `plane/bgtasks/testing_artifact_task.py`                                    |
| Coverage / overview / release-gate computation                            | `plane/app/views/testing/report.py`                                         |
| Demo seed (composed modules, goes through the service layer)              | `plane/testing/demo/` + `plane/db/management/commands/seed_testing_demo.py` |

Tests (canonical usage examples — read these before changing behavior):

- `plane/tests/contract/api/test_testing_management.py` — full API-key lifecycle: folder → case → version bump → link → run → fail → defect → retest → close → reports; plus 403/400/409 rejection paths.
- `plane/tests/contract/api/test_testing_automation.py` — idempotency replay/conflict, shared app+public idempotency store.
- `plane/tests/contract/app/test_testing_{capability,library,runs}.py`, `plane/tests/unit/testing/`, `plane/tests/unit/models/test_testing_library.py`.

## Delivery surfaces (`apps/api/`, fork-owned, no service layer)

These have thinner plumbing than testing: model invariants in `save()`/`clean()`, logic in the view. That is deliberate — none of them has a second caller, and a service layer with one consumer is indirection, not architecture. Add one the moment a second tree needs the same logic.

| Surface                                                           | Backend                                                                                       | Web                                              |
| ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| Project Overview (progress, activity, links, milestones, updates) | `plane/app/views/project/overview.py`                                                         | `.../projects/(detail)/[projectId]/overview/`    |
| Noticeboard (`EntityUpdate`, `EntityUpdateLabel`)                 | same file — `EntityUpdateViewSet`                                                             | `apps/web/core/components/updates/panel.tsx`     |
| Customer frontline (intake grouped by a chosen property)          | same file — `ProjectFrontlineEndpoint`                                                        | `.../overview/frontline-panel.tsx`               |
| Needs attention (overdue + urgent)                                | same file — `ProjectAttentionEndpoint`                                                        | `.../overview/attention-panel.tsx`               |
| Release readiness on the overview                                 | reads `testing/overview`'s `release_gate`                                                     | `.../overview/readiness-panel.tsx`               |
| Work-item types & properties                                      | `plane/db/models/{issue_type,work_item_property}.py`, `plane/app/views/work_item_property.py` | `apps/web/core/components/work-item-extensions/` |
| Requirement nature (`Issue.requirement_kind`)                     | `plane/db/models/issue.py`; `/api/v1` serializer only                                         | no UI — the app-tree serializer omits the field  |
| Delivery states (`DEFAULT_STATES`, 14-state `SDLC_STATES`)        | `plane/db/models/state.py`                                                                    | project settings → states                        |
| Page folders (`Page.is_folder`)                                   | `plane/db/models/page.py`, `plane/app/views/page/base.py`                                     | `apps/web/core/components/pages/list/`           |
| Milestones                                                        | `plane/db/models/portfolio.py`; both trees                                                    | overview milestones panel                        |
| Intake ingestion                                                  | `plane/db/models/intake.py`, `plane/app/views/intake/`                                        | `.../projects/(detail)/[projectId]/intake/`      |
| Automations, state transitions, templates                         | `plane/db/models/automation.py`, `plane/app/urls/project.py`                                  | project settings                                 |

**The Overview surface is app-tree only.** `overview/`, `progress/`, `activity/`, `updates/`, `frontline/`, `attention/` exist under `/api/workspaces/...` (session auth) and have no `/api/v1` equivalent, so no API key reaches them and no MCP tool wraps them. Milestones and links are the exceptions — both trees. Before adding a `/api/v1` mirror, read the app-tree-only note in api-reference.md: an agent can already feed these panels through the entities they read from.

Tests: `plane/tests/contract/app/test_noticeboard.py` (posting, revising, filing, taking down, permission boundary), `test_frontline_and_attention.py` (grouping, triage folding, caps, ordering), `test_endpoint_smoke.py` (every project-scoped GET asserted not to 5xx — new routes are covered the day they are registered).

## TypeScript tooling

| Package             | Location                 | Key files                                                                                                                             |
| ------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| SDK `@plane/qa-sdk` | `packages/qa-sdk/src/`   | `client.ts` (PlaneQAClient, retry, resolvers), `errors.ts`, `schemas.ts` (zod), `types.ts`                                            |
| CLI `@plane/qa-cli` | `apps/plane-qa-cli/src/` | `commands.ts` (dispatch), `run.ts` (exit codes, confirmation), `arguments.ts`, `config.ts`, `help.ts`                                 |
| MCP `@plane/qa-mcp` | `apps/plane-qa-mcp/src/` | `create-server.ts` (all 50 tool registrations + annotations), `server.ts` (stdio launcher), `results.ts` (truncation, error wrapping) |

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
- `docs/planning/testing-product-definition.md` — personas, JTBD map, traceability design principles, the prioritised UX gap backlog, and the interface specs for case detail, execution workspace, and the work-item testing panel.
- `docs/planning/project-overview-noticeboard.md` — why the Overview became a product war room: the three data classes (derived / triage / first-hand) and the interaction rule each one implies, the layout, and the read/write path per panel. Read this before adding anything to that page; it is the argument for why a computed number never gets an editable field beside it.
- `docs/process/plane-qa-guideline.md` — the delivery process this fork models, in Traditional Chinese. §B0 is the diagram the demo seed instantiates; §B1 the four-level vocabulary; §B2 why requirement nature is a field on `Issue` and neither a type nor a property. Read B2 before adding anything that classifies requirements.
- `docs/demo/ai-software-delivery-demo.md` — the AIDEMO seed. The DEMO seed's usage lives in `.agents/skills/plane-qa/references/demo-data.md`.
- `docs/architecture/decisions/0001..0007` — ADRs (case aggregate/versioning, immutable execution, automation ingestion, milestones/fork boundaries, project attributes & entity updates, page folders as pages, folders declared not inferred). **0005 predates the war-room redesign.** Its `EntityUpdate` and activity-feed decisions still hold, and `Project.priority/start_date/target_date` are still on the model — but the Properties panel that surfaced them was removed, because an editable field beside a computed number produces two truths and no owner. Schema decision stands; presentation decision superseded by the noticeboard spec.
- `docs/operations/plane-qa-agent-tooling.md` — runbook, troubleshooting.
- `.agents/skills/plane-qa/` — cross-agent skill (Codex entry via `agents/openai.yaml`) and the single source of truth for all shared reference docs, including this file.
- `.claude/skills/operating-plane-qa/` — Claude Code entry point; thin SKILL.md that links into `.agents/skills/plane-qa/references/`.

## Invariants to preserve when changing code

1. `TestCaseVersion`, `TestStep`, `TestResult` raise on update — keep immutability in the model layer, not just views.
2. Every model's `clean()` enforces same-workspace/same-project across all FKs; new FKs must join that check.
3. Case edit = `publish_test_case_version` (new version + pointer bump) in one transaction.
4. Run creation pins versions; completed runs must keep rejecting results and membership changes.
5. Defect creation stays atomic (Issue + `TestResultIssueLink` in one transaction) and limited to failed/blocked.
6. Idempotency = unique `(project, idempotency_key)` + canonical payload hash; replay 200, mismatch 409.
7. Release status must never depend on Celery completion — transactional rows are authoritative.
8. Prefer extension seams over upstream edits; Testing keeps its own migration chain — never edit upstream migrations (see `docs/architecture/testing-platform-workflow.md` §10 for fork/rebase strategy).

### Delivery-side invariants

9. **No category name is compiled into the product.** Noticeboard topics are the project's `Label`s; the frontline panel groups by whichever `WorkItemProperty` carries `is_grouping_dimension`. A hardcoded "customer"/"market"/"escalation" enum would be wrong for the next team, and there is no reason to make everyone think in one team's vocabulary. If you find yourself adding a choice field of category names, the answer is a pointer to user data instead.
10. **One grouping dimension per project**, enforced by a partial unique constraint, and only on `select`/`multi_select` — grouping by free text makes one bucket per typo. A UI that sets it must clear the outgoing holder first, or the constraint surfaces as a button that appears to do nothing.
11. **`EntityUpdate.edited_at` is stamped only when the text changes.** `updated_at` moves for reasons a reader does not care about, so it cannot answer "was this changed after I read it". Attaching a topic is filing, not revision.
12. **An announcement belongs to its author, or to a project admin.** Editing someone else's post changes what they are recorded as having said; admins keep the ability because a board nobody can moderate is its own problem.
13. **Derived panels are never editable in place.** Progress, milestones, attention and readiness are computed; the way to change them is to open the source. An editable field beside a computed number produces two truths and no owner — that is why the Properties panel was removed.
14. **A capped list says what it held back.** `total_overdue`, `total_urgent` and a group's `total` exist so five never reads as all there is.
15. **Panels with nothing to say render nothing.** No grouping dimension → no frontline panel; nothing overdue → no attention panel. A panel that says "all clear" daily trains people to skip the region where the alarm will appear.
16. **The two classification axes stay separate.** `IssueType.level` carries breadth; `Issue.requirement_kind` carries nature. Fold either into the other and the number of types becomes their product — this workspace reached nine types that way, and `converge_work_item_types` exists to undo it. Any new classification question gets a field or a property, never a type per combination.
17. **Coverage counts promises, once each.** Only `needs_acceptance` types produce rows, `backlog`/`cancelled` are out of scope, and a row summarising other counted rows contributes nothing to the totals. Contracts still roll up from children that earn no row of their own — the walk down the hierarchy is independent of who is counted.
18. **A page folder is declared, not inferred** (`Page.is_folder`, ADR 0007). Inferring it from "has children" makes a page change kind when its last child moves, and gives a folder no way to exist while empty.
