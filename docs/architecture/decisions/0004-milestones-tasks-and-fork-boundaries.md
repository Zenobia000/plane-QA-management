# ADR 0004: Milestones, task boundaries and fork maintenance

- Status: Accepted
- Date: 2026-07-14

## Context

Testing spans Plane's Web, App API, Public API, PostgreSQL, worker and object storage containers. Shipping horizontal
layers independently would create dead UI, unverifiable migrations and duplicate policy implementations. The fork must
also remain mergeable with upstream Plane.

## Decision

Delivery uses the WBS milestone exits in `docs/planning/testing-platform-wbs.md`:

- M0 proves navigation, authorization and build seams.
- M1 delivers one complete library-to-fixed-execution journey.
- M2 closes requirement, defect, retest and release evidence.
- M3 maps automation into the same aggregates and reports.
- M4 proves source images, portability, restore and upstream rehearsal.

A development task is vertically scoped when possible: model invariant, shared application service, App/Public adapter,
typed client/store, native UI and acceptance evidence. App and Public API views may translate authentication and payloads
but must not duplicate state transitions. Database migrations are append-only and never renumber upstream migrations.

Fork-owned code uses a `testing` module/route/package boundary. Changes to shared upstream surfaces are intentionally
narrow: model exports, URL aggregation, root store registration, project navigation, Work Item summary insertion and
FileAsset entity type. Every such seam is listed in the upstream rehearsal runbook and is reviewed first during merges.

## Definition of done

A WBS item is done only when its acceptance artifact exists and its named test gate has actually run. Static compilation
does not prove runtime, image, restore or browser journeys. A milestone exits only when all included items are done and
the previous milestone's journeys remain green against a migrated PostgreSQL database.

## Consequences

- Partially implemented layers remain ACTIVE even when they compile.
- Shared application services make manual and automated evidence comparable.
- Upstream conflicts concentrate in a documented, small seam list.
- Operational recovery is part of product completion, not a post-release note.
