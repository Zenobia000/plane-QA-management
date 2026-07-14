# ADR 0002: Fixed test runs and append-only execution results

- Status: accepted
- Date: 2026-07-14
- Owners: Plane localhost fork maintainer
- Related work items/test cases: WBS 3.1–3.9

## Context

A test run is evidence for a particular scope and build. Library content can change while a run is active or after it
closes. A mutable reference to the current test case would make old results ambiguous. Retesting must also preserve the
original failure rather than replacing it with the latest status.

## Decision

- `TestRun` is project-scoped and optionally links to an existing Plane Cycle and Module.
- The first supported selection mode is `fixed`; creation resolves case IDs and pins each current `TestCaseVersion` in
  one transaction.
- `TestRunCase` retains the pinned version, stable position, and a denormalized latest status for efficient progress.
- `TestResult` is append-only. Retest increments its sequence and never updates the prior result.
- Allowed result values are `passed`, `failed`, `blocked`, and `skipped`; a run case with no results is `open`.
- A completed run rejects membership and result mutations.
- Closing a run is explicit and records `closed_at`.

## Consequences

Fixed runs are immediately auditable and sufficient for the manual-testing MVP. Live query plans remain a later additive
feature. Progress reads are cheap, while the result table remains the historical source of truth.

## Verification

- A fixed run continues to expose version 1 after the library publishes version 2.
- Two retests create two result rows and update only the denormalized latest status.
- Closed runs reject new results.
- Cycle, Module, cases, and versions cannot cross project boundaries.

## Architecture diff

Adds TestRun, TestRunCase, and TestResult to the Testing domain in PostgreSQL and transactional execution services in
the Django API container. No container boundary changes.
