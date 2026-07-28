# Native Testing Platform — Development WBS

Baseline: Plane `preview` at `d3d3de44`
Delivery target: independently maintained localhost repository
Architecture contract: `docs/architecture/testing-platform-workflow.md`

## Status legend

- `DONE`: implemented and verified
- `PARTIAL`: some of the stated deliverable ships; the shortfall is named in the row
- `ACTIVE`: currently being implemented
- `READY`: dependencies satisfied
- `BLOCKED`: missing prerequisite or decision
- `BACKLOG`: not yet ready

## 0. Program governance

| WBS | Work package                              | Depends on | Deliverable / acceptance                                            | Tests                | Status |
| --- | ----------------------------------------- | ---------- | ------------------------------------------------------------------- | -------------------- | ------ |
| 0.1 | Pin upstream baseline                     | —          | Commit and branch recorded in architecture docs                     | `git rev-parse HEAD` | DONE   |
| 0.2 | C4 and information-flow model             | 0.1        | Context, container, component and domain diagrams                   | Documentation review | DONE   |
| 0.3 | Delivery and reverse-engineering workflow | 0.2        | DoR, DoD, discovery trace and fork strategy                         | Checklist review     | DONE   |
| 0.4 | WBS and dependency map                    | 0.2        | This document; every package has acceptance and test gates          | `git diff --check`   | DONE   |
| 0.5 | ADR set                                   | 0.3        | Accepted ADRs for aggregate, versioning, APIs, milestones and tasks | Architecture review  | DONE   |

## 1. Architecture-enabling vertical slice

Goal: prove that Testing can enter Plane through narrow extension seams before adding schema complexity.

| WBS | Work package                     | Depends on | Deliverable / acceptance                                                   | Tests                                     | Status |
| --- | -------------------------------- | ---------- | -------------------------------------------------------------------------- | ----------------------------------------- | ------ |
| 1.1 | Project navigation entry         | 0.4        | Testing appears after Intake and respects project permissions              | Type check; navigation review             | DONE   |
| 1.2 | Testing route and header         | 1.1        | `/projects/:projectId/testing` renders inside authenticated project layout | Production web build                      | DONE   |
| 1.3 | Plane-native empty state         | 1.2        | Explains library/run/report direction without dead controls                | Responsive/manual smoke                   | DONE   |
| 1.4 | Capability endpoint              | 0.4        | Authenticated project member receives stable capability payload            | API contract tests                        | DONE   |
| 1.5 | Unauthorized isolation           | 1.4        | Anonymous and non-project users cannot probe project Testing               | API contract tests                        | DONE   |
| 1.6 | Frontend typed capability client | 1.4        | `@plane/services` exposes typed request and error behavior                 | Type check; unit test when harness exists | DONE   |
| 1.7 | Slice integration                | 1.2, 1.6   | Page loads capability and exposes explicit loading/error/ready states      | Acceptance smoke                          | DONE   |

Exit gate: backend contracts pass, frontend type/build passes, existing localhost deployment remains untouched.

Exit evidence: capability authorization contracts pass in PostgreSQL, the production Web image builds, and the
source-built API/Web containers return HTTP 200 in the isolated localhost rehearsal stack.

## 2. Test Case Library MVP

| WBS  | Work package                  | Depends on | Deliverable / acceptance                                                                                                                                            | Tests                                                          | Status  |
| ---- | ----------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- | ------- |
| 2.1  | ADR: TestCase aggregate       | 0.5        | Ownership, identity and work-item link decision accepted                                                                                                            | ADR review                                                     | DONE    |
| 2.2  | TestFolder model              | 2.1        | Project-scoped nested folders with ordering and soft delete                                                                                                         | Model constraints; cross-project tests                         | DONE    |
| 2.3  | TestCase model                | 2.1        | Stable case identity, folder, lifecycle and sequence                                                                                                                | Model/unit tests                                               | DONE    |
| 2.4  | TestCaseVersion and steps     | 2.3        | Immutable versions and ordered structured steps                                                                                                                     | Concurrency/invariant tests                                    | DONE    |
| 2.5  | Library application services  | 2.2–2.4    | Create, edit-as-new-version, move and archive transactions                                                                                                          | Service tests                                                  | DONE    |
| 2.6  | App API                       | 2.5        | CRUD, search, filtering and cursor pagination                                                                                                                       | Contract/auth tests                                            | DONE    |
| 2.7  | Typed services and MobX store | 2.6        | Normalized state with request deduplication and rollback                                                                                                            | Store/service unit tests                                       | DONE    |
| 2.8  | Folder/list/detail UI         | 2.7        | Case list and detail editor ship. **Folders render as a flat list although `TestFolder.parent` nests, and the detail editor is a third column, not a peek overlay** | Static-render component tests; no accessibility audit recorded | PARTIAL |
| 2.9  | Requirement links             | 2.5        | Typed links between TestCase and Plane Work Item                                                                                                                    | Cross-project and API tests                                    | DONE    |
| 2.10 | Library acceptance journey    | 2.8, 2.9   | Create, edit, preserve old version, link requirement                                                                                                                | Manual rehearsal, 2026-07-14                                   | DONE    |

Exit evidence: model, contract, CSV round-trip and PostgreSQL concurrency tests pass; MobX deduplication/rollback and
component acceptance tests pass; the Testing Library is included in the production Web image.

## 3. Test Run and manual execution MVP

| WBS | Work package                 | Depends on | Deliverable / acceptance                                         | Tests                                         | Status |
| --- | ---------------------------- | ---------- | ---------------------------------------------------------------- | --------------------------------------------- | ------ |
| 3.1 | ADR: immutable execution     | 2.1        | Version pinning, result append and close semantics accepted      | ADR review                                    | DONE   |
| 3.2 | TestRun models               | 2.4, 3.1   | Draft/active/completed run scoped to project/build/cycle/module  | Model tests                                   | DONE   |
| 3.3 | Fixed selection builder      | 3.2        | Resolve selection and pin case versions atomically               | Transaction/concurrency tests                 | DONE   |
| 3.4 | Result state machine         | 3.2        | Open/pass/fail/block/skip and append-only retest                 | Unit/model tests                              | DONE   |
| 3.5 | Run APIs and client state    | 3.3, 3.4   | List, create, execute, close and filter endpoints                | API/store tests                               | DONE   |
| 3.6 | Run builder UI               | 3.5        | Details, selection, configuration, preview, create               | Static-render component tests                 | DONE   |
| 3.7 | Execution workspace          | 3.5        | Case queue, pinned detail, sticky result actions, next-case flow | Static-render tests; keyboard flow unverified | DONE   |
| 3.8 | Progress summaries           | 3.4        | Transactionally correct status counts and latest result          | Query/service tests                           | DONE   |
| 3.9 | Execution acceptance journey | 3.6–3.8    | Build fixed run, mutate library, execute without history drift   | Manual rehearsal, 2026-07-14                  | DONE   |

Exit evidence: fixed selection/version pinning, concurrent result sequencing, append-only retest, close protection,
progress serialization, store transitions and execution component states pass their automated gates.

## 4. Defect and retest integration

| WBS | Work package            | Depends on | Deliverable / acceptance                               | Tests                   | Status |
| --- | ----------------------- | ---------- | ------------------------------------------------------ | ----------------------- | ------ |
| 4.1 | Result–Issue link model | 3.4        | Typed defect relation in the same project              | Constraint/auth tests   | DONE   |
| 4.2 | Create defect command   | 4.1        | Issue and link created atomically from failed evidence | Service/API tests       | DONE   |
| 4.3 | Prefilled defect UX     | 4.2        | Environment, steps, expected, actual and source links  | Static-render tests     | DONE   |
| 4.4 | Ready-for-retest state  | 4.1        | Resolved defect is visible from execution context      | Query/integration tests | DONE   |
| 4.5 | Retest workflow         | 4.4        | New result retained beside original failure            | State/E2E tests         | DONE   |

## 5. Reporting and release readiness

| WBS | Work package              | Depends on | Deliverable / acceptance                                                                                                                               | Tests                            | Status |
| --- | ------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------- | ------ |
| 5.1 | Reporting query contracts | 3.8, 4.5   | Exact definitions of coverage, latest result and readiness                                                                                             | Golden-data tests                | DONE   |
| 5.2 | Testing overview          | 5.1        | Active run, failures, blockers, uncovered work and retests                                                                                             | Query/UI tests                   | DONE   |
| 5.3 | Requirement coverage      | 2.9, 5.1   | Covered/uncovered and execution state by work item, rolled up the parent hierarchy with defects excluded                                               | Query/contract tests             | DONE   |
| 5.4 | Run scorecard             | 5.1        | Comparable status/configuration summaries                                                                                                              | Golden-data tests                | DONE   |
| 5.5 | Release gate view         | 5.2–5.4    | Ready/not-ready with explainable blockers: failures, blocks, open defects, unexecuted cases, and scheduled requirements holding no acceptance contract | Contract tests; DEMO measurement | DONE   |

## 6. Automation ingestion

| WBS | Work package                | Depends on | Deliverable / acceptance                               | Tests                        | Status |
| --- | --------------------------- | ---------- | ------------------------------------------------------ | ---------------------------- | ------ |
| 6.1 | Public API ADR and schema   | 3.4        | Auth, identifiers, idempotency and partial errors      | OpenAPI/ADR review           | DONE   |
| 6.2 | Shared application services | 6.1        | App and public adapters share transitions and policies | Parity contract tests        | DONE   |
| 6.3 | Idempotent ingestion        | 6.2        | Repeated upload cannot duplicate run/results           | Concurrency/API tests        | DONE   |
| 6.4 | Artifact processing         | 6.3        | After-commit Celery upload to MinIO with diagnostics   | Task/integration tests       | DONE   |
| 6.5 | JUnit adapter               | 6.3        | Documented mapping and actionable unmapped results     | Fixture/import tests         | DONE   |
| 6.6 | CI acceptance               | 6.4, 6.5   | Upload, retry and report visible in release view       | Manual rehearsal, 2026-07-14 | DONE   |

## 7. Data portability and operations

| WBS | Work package                    | Depends on | Deliverable / acceptance                              | Tests                | Status |
| --- | ------------------------------- | ---------- | ----------------------------------------------------- | -------------------- | ------ |
| 7.1 | CSV import/export               | 2.6        | Round-trip cases, steps, folders and links            | Golden fixture tests | DONE   |
| 7.2 | Source-built Docker images      | 1.7        | Fork frontend/backend images replace official images  | Image build/smoke    | DONE   |
| 7.3 | Database backup/restore runbook | 2.4        | Tested PostgreSQL and MinIO recovery procedure        | Restore drill        | DONE   |
| 7.4 | Upgrade migration rehearsal     | 7.2, 7.3   | Sanitized copy upgrades from current localhost data   | Migration/E2E        | DONE   |
| 7.5 | Upstream merge rehearsal        | 1.7        | Conflict log and repeatable upstream update procedure | Full affected suite  | DONE   |

Operations packages remain non-`DONE` until a dated record exists under `docs/operations/rehearsals/`. The scripts and
runbook are the procedure, not evidence that the destructive restore, upgrade, or upstream-merge drill succeeded.

Current verification note (2026-07-14): the Web Vitest suite passes (2 files, 6 tests), Web TypeScript checking passes,
and `git diff --check` passes. Source Web/API images build, a new PostgreSQL database migrates through Testing migrations
0122–0125, all localhost containers start, Web reaches API, Live starts, and the Caddy entry point returns HTTP 200. See
`docs/operations/rehearsals/2026-07-14-localhost-source-smoke.md`. Restore, current-copy schema-upgrade, and isolated
upstream-merge drills are recorded alongside it. The complete authenticated browser, CSV, JUnit retry, and artifact
journeys are recorded in `docs/operations/rehearsals/2026-07-14-authenticated-browser-acceptance.md`.

## Accuracy audit (2026-07-28)

Every package here read `DONE`. Two rows did not survive checking against the tree, and one verification method was
recorded that the repository does not possess.

**`2.8` claimed a folder tree and a peek editor; neither exists.** Folders render as a flat list even though
`TestFolder.parent` nests them, and the detail editor is the third column of the library view. The peek overlay is
specified in section 4 of `testing-product-definition.md` and has not been built. Folder delete and rename were also
absent until 2026-07-28, and no test caught it.

**`5.5` claimed explainable blockers.** Seeding the DEMO project produced `release_gate.ready = true` while a story held
no acceptance contract at all, so the blocker set is incomplete. Tracked as #18 in the product definition.
**Closed on 2026-07-28** by `9ed58492d`: a scheduled requirement with no contract is now a blocker, `backlog` and
`cancelled` state groups are exempt, and four contract tests in `test_testing_runs.py` hold the behaviour. `5.3` moved
with it — coverage now rolls up the parent hierarchy and excludes defects, and the overview reports library tidiness
and requirement coverage as two separate figures rather than one that conflated them.

**`E2E acceptance` appears as the verification method for several packages, and no end-to-end harness exists** — there
is no Playwright or Cypress configuration anywhere in the repository. What was actually done is recorded under
`docs/operations/rehearsals/`: five dated manual runs from 2026-07-14. Those are real evidence that the journey worked
once; they are not a gate that stops it breaking. The affected rows now name the method genuinely used.

The distinction matters because this document's own change-control rule requires listed acceptance evidence before a
package moves to `DONE`. Where the listed evidence is a harness that does not exist, the rule cannot bind.

## Milestones

| Milestone                         | Included WBS | Outcome                                                           |
| --------------------------------- | ------------ | ----------------------------------------------------------------- |
| M0 Extension seam proven          | 0.x, 1.x     | Testing is a native, authorized Plane surface with passing gates  |
| M1 Spreadsheet replacement        | 2.x, 3.x     | Reusable case library and manual execution                        |
| M2 Closed quality loop            | 4.x, 5.x     | Requirement-to-defect-to-retest traceability and release evidence |
| M3 Automation-ready               | 6.x          | CI results join the same quality model                            |
| M4 Maintainable localhost product | 7.x          | Source images, recoverability and upstream upgrade discipline     |

## Change-control rule

No work package moves to `DONE` until its listed acceptance evidence exists. If implementation discovers a new cross-container relationship, persistence invariant, public contract, or trust boundary, update the C4 document and add/modify an ADR before merging the work package.
