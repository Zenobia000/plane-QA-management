# ADR 0003: Automation ingestion public API and idempotency

- Status: Accepted
- Date: 2026-07-14

## Context

CI systems retry requests, JUnit has no Plane identity, and the same automated test must contribute to the same
quality history as manual execution. Creating a second execution on retry would corrupt run counts and release gates.

## Decision

Expose `POST /api/v1/workspaces/{slug}/projects/{project_id}/testing/automation-ingestions/` through Plane's existing
`X-API-Key` authentication, project permission and rate limiting. The App API exposes the same command for interactive
clients. Both adapters invoke `plane.testing.ingest_automation_results`; neither owns domain transitions.

Every request requires `Idempotency-Key`. `TestAutomationIngestion` uniquely owns `(project, idempotency_key)` and stores
a SHA-256 hash of the canonical semantic payload. An identical replay returns HTTP 200 and the original run. Reusing a
key with a different payload returns HTTP 409. A project row lock serializes identity resolution and ingestion creation.

`TestCaseAutomationLink(source, external_id)` provides stable mapping. An unseen identity creates one tagged automated
TestCase and reports that action in diagnostics; later uploads reuse it. Each upload creates a fixed run pinned to the
then-current TestCaseVersion and records results through the same append-only service used by manual execution.

JUnit identities are `classname::name`; failures and errors map to failed, skipped maps to skipped, and all other cases
map to passed. XML is capped at 5 MiB and rejects DTD/entity declarations before parsing. Invalid generic result rows are
reported as partial diagnostics while valid rows are committed atomically; an upload with no valid rows is rejected.

## Consequences

- CI retry is safe and manual/automated reporting shares one definition.
- Renaming a JUnit test changes its identity unless the producer supplies a stable generic `external_id`.
- Auto-created cases are visible and can be enriched by testers without breaking prior pinned runs.
- Artifact bytes remain in Plane's FileAsset/MinIO path; ingestion only retains typed references and diagnostics.

## Verification

- Contract: identical replay does not increase run/result counts.
- Contract: conflicting replay returns 409.
- Unit: JUnit status, duration and unsafe XML mapping.
- Contract: API key project isolation is inherited from `ProjectEntityPermission` and tested with public API fixtures.
