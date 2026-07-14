# Authenticated browser acceptance — 2026-07-14

Scope: the release-blocking journeys in architecture section 9.2 and the runtime acceptance step in the upstream
runbook, executed against the source-built localhost stack through its published Caddy origin.

## Environment

- Entry point: `http://localhost` (Chromium, 1440 × 1000, headless).
- Dedicated local account, workspace `browser-acceptance`, and project
  `c8bfc63a-9f2b-45c6-8f3d-e9f81ce67ae4`; no system password was used by the browser test.
- API and Web were rebuilt from the current worktree as `plane-testing-api:dev` and `plane-testing-web:dev`.
- The browser used normal email/password authentication and the same session/CORS/CSRF path as a user.

## Defects discovered and corrected

1. Login redirected to the unpublished development port because the source overlay inherited
   `APP_BASE_URL=http://localhost:3000`. The overlay now supplies `APP_BASE_URL=http://localhost` to every API image
   service; a real login now reaches onboarding/workspace routes through Caddy.
2. Testing page files and navigation existed, but the explicit React Router table omitted the Testing route. Added
   the project-detail layout/route registration; the sidebar link now resolves instead of rendering the catch-all 404.
3. Overview, Library, and Runs read MobX state outside `observer` component boundaries. Their API calls returned 200
   but the UI remained in `Loading quality overview…`. All three views now react to asynchronous store updates.
4. Reporting counted defect/link rows whose parent Testing aggregate had been soft-deleted while Celery cleanup was
   pending. Overview and coverage now constrain parent liveness; four Testing run contracts, including both new
   regression assertions, pass.
5. `process_testing_artifacts` was not in `CELERY_IMPORTS`; the worker discarded it as an unregistered task. The task
   is now registered explicitly and appears in the worker startup registry.
6. Defect creation did not yet prefill every WBS 4.3 diagnostic field. It now includes the run environment,
   preconditions, ordered action/expected steps, actual result, and a browser-facing Testing source link in both the
   rendered description and structured description data.

## Browser journey result

PASS. A single uninterrupted browser run completed these assertions:

1. Signed in and loaded the native project Testing route. Overview, Library, and Runs rendered from six successful
   Testing API reads.
2. Created two test cases and linked both to the same Plane work item. Cross-project denial remains covered by the
   PostgreSQL API contract suite.
3. Created a fixed run containing case version 1, then edited the Library case to version 2 with preconditions and two
   ordered steps. Reopening the run still rendered the original v1 title and `Case 1 · v1`.
4. Recorded a failed result with actual evidence text using the `F` keyboard shortcut, created the prefilled Plane
   defect, verified its diagnostic fields, moved that defect to a completed state through the authenticated Plane
   issue API, reloaded the run, and observed `Ready for retest`.
5. Recorded a passing retest with the `P` keyboard shortcut, closed the run, and asserted the append-only result
   history was exactly `failed → passed`.
6. Reloaded Overview and observed 100% case-to-requirement linkage and `Release gate: Ready`.
7. Repeated the route smoke at a 390 × 844 mobile viewport; Testing and Library rendered with the tab navigation
   available.

Final successful browser record:

- Cases: `d580dd1b-c015-4b4f-ba87-976385834272`, `370b4568-abf4-4eef-b547-1b5c65f5284e`.
- Run: `30fdfb78-f12e-437f-a718-8c93c5663010`.
- Defect: `3715fac4-858c-4c83-a9d1-d932bc8ca8af`.
- Testing HTTP errors: 0; unexpected page errors: 0.
- The static production shell emitted existing React hydration codes 418/423 and unrelated pre-auth/Intake console
  noise. These were recorded separately and did not correspond to a failed Testing request or assertion.

## Portability and automation result

PASS.

- Exported the Library through the visible CSV control (2,724 bytes on the final run), verified versioned
  preconditions/steps were present, and imported it through the visible file control; 13 cases were created from that
  accumulated rehearsal export. Golden contract tests remain the deterministic clean round-trip gate.
- Submitted JUnit through the authenticated App ingestion endpoint with one uploaded FileAsset, then retried the exact
  payload and idempotency key. First response was 201, retry was 200 with `replayed: true`, and both referenced the same
  ingestion and run.
- Ingestion `7b063ffa-c0e8-43d5-b29e-8ff078206e23` produced run
  `f6fcf21a-a17e-4cfd-9fbc-8a9f253d1926`, one result, one idempotency row, and one run.
- Worker processing changed FileAsset `73ce0419-c3c4-44c2-9150-966dbffa767d` to entity type
  `TESTING_ARTIFACT` with entity identifier equal to the ingestion ID.

## Supporting gates

- Web Vitest: 2 files, 6 tests passed.
- Web TypeScript: passed.
- Production Web build/image: passed after route/reactivity fixes.
- Full affected backend suite: 29 passed after the stale-parent reporting and Celery-registration fixes.
- Worker startup registry contains `plane.bgtasks.testing_artifact_task.process_testing_artifacts`.
- Previous contract evidence covers anonymous/non-member isolation, cross-project rejection, concurrency, CSV golden
  round-trip, JUnit mapping/conflict behavior, and artifact project isolation.
- The current-copy upgrade and restore evidence remains in the adjacent dated rehearsal records.

## Result

PASS. All six critical architecture journeys now have runtime or destructive-copy evidence, and the full authenticated
browser path proves the UI, App APIs, Plane issue workflow, reporting, CSV, automation idempotency, Celery, and artifact
association work together through the localhost deployment.
