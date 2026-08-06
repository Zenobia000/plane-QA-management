# Plane QA — codebase map (for modifying the platform)

The fork owns two halves. **Testing** is the QA domain below; **delivery** is everything this fork added to Plane's project management — work-item types and properties, milestones, initiatives, intake, automations, state transitions, templates, and the Project Overview. They share one project scope, and the split matters when deciding where code goes: testing has a service layer, delivery mostly does not.

Layering rule (testing): business logic lives only in `apps/api/plane/testing/` (framework-agnostic, `@transaction.atomic`, locks Project via `select_for_update`). Views are thin adapters; the public API subclasses the app views adding only auth/throttle/error-envelope. Never duplicate logic into a view, and never let SDK/CLI/MCP import Django code or touch the DB.

## Backend (Django, `apps/api/`)

| Layer                                        | Location                                                                |
| -------------------------------------------- | ----------------------------------------------------------------------- |
| Models (invariants in `clean()`)             | `plane/db/models/availability.py`                                       |
| Working days, holidays, make-up days         | `plane/availability/calendars.py`                                       |
| Reachable windows + cross-zone intersection  | `plane/availability/schedule.py`                                        |
| Services (the only write path)               | `plane/availability/services.py`                                        |
| Permission (members only, guests barred)     | `plane/app/views/availability/permissions.py`                           |
| App views (session auth)                     | `plane/app/views/availability/{capability,schedule,settings}.py`        |
| App URLs                                     | `plane/app/urls/availability.py`                                        |
| Public views (`X-API-Key`, thin subclasses)  | `plane/api/views/availability.py`                                       |
| Public URLs                                  | `plane/api/urls/availability.py`                                        |
| Serializers                                  | `plane/app/serializers/availability.py`                                 |
| Seed (fixed-date holidays only)              | `plane/db/management/commands/seed_work_calendars.py`                   |
| Types                                        | `packages/types/src/availability.ts`                                    |
| HTTP service (app tree)                      | `packages/services/src/availability/availability.service.ts`            |
| MobX store                                   | `apps/web/core/store/availability.store.ts`                             |
| Route + tabs (Hours / Time off / Allocation) | `apps/web/app/(all)/[workspaceSlug]/(projects)/calendar/`               |
| Sidebar entry (ADMIN + MEMBER only)          | `packages/constants/src/workspace.ts`                                   |
| SDK / CLI / MCP                              | `client.ts` availability methods; `availability` CLI group; 4 MCP tools |
| i18n                                         | `packages/i18n/src/locales/*/team-calendar.json`                        |

Settings live at `/calendar/settings`, split by who owns the answer: my working hours (the member), work calendars and leave types (admin). The settings tab is the one tab **not** gated on a capability flag — it is where the data gets created, so gating it would leave a fresh workspace unable to configure anything.

Two rules that are easy to break by accident:

1. **Everything is UTC across the wire.** Local wall-clock times exist only on a member's own profile. `"Tuesday 09:00"` is not comparable across cities, and comparing across cities is what this surface is for. Zone resolves profile → calendar → `User.user_timezone`.
2. **Only approved absences bind.** A pending request has not been decided; planning against it is planning against a guess. Cancelling and rejecting keep the row so history stays honest.
3. **A member's allocations total 100% or less**, refused at the write rather than flagged. Leave reduces every project in proportion — nobody takes leave _from a project_.
4. **Reasons are redacted by omission**, not by nulling the field — a present key still says there was a reason. Enforced in the serializer, never in a component.
5. **A make-up workday counts however the weekday mask reads.** Taiwan works some Saturdays to bridge long weekends; a weekday-mask-plus-holiday-list model cannot express that day, and every span containing one silently comes out short. The seed command deliberately ships no lunar or make-up dates — they are announced yearly, and a guessed date is worse than none.

Tests: `plane/tests/unit/availability/` (working days, cross-zone overlap, DST), `plane/tests/contract/app/test_availability_{capability,schedule}.py`, `plane/tests/contract/api/test_availability.py`, `plane/tests/unit/management/test_seed_work_calendars.py`.

The capability endpoint reports a false flag per unbuilt slice and the client renders an empty state for each, so the navigation, route and three tabs shipped before any migration existed. Flipping a flag belongs to the slice that earns it — see `docs/planning/team-calendar-wbs.md`.

A service layer (`plane/availability/`) arrives with the first slice that writes: unlike the delivery surfaces, this one has four consumers from the start — app tree, `/api/v1`, MCP and CLI.

Docs: `docs/architecture/decisions/0008-availability-is-a-workspace-fact.md`, `docs/planning/team-calendar.md` (the three questions, the three kinds of "time", the four screens), `docs/planning/team-calendar-wbs.md`.

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
