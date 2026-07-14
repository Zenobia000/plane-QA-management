# ADR 0001: Independent and immutable Test Case aggregate

- Status: accepted
- Date: 2026-07-14
- Owners: Plane localhost fork maintainer
- Related work items/test cases: WBS 2.1–2.10, 3.1–3.9

## Context

Plane Work Items represent completable delivery work. Test cases are reusable quality assets that survive cycles, execute
many times, and must retain the exact instructions used for historical results. Modeling a test case as a specialized
Work Item would couple its lifecycle to states, estimates, assignees, and archive behavior that do not express test
evidence.

Editing a test case after an execution must not rewrite what a tester actually executed. Test runs therefore need a
stable version identity rather than a mutable reference to the latest library content.

## Decision drivers

- Preserve trustworthy historical execution evidence.
- Keep Plane Work Item behavior unchanged and easy to merge with upstream.
- Support manual and automated execution through the same identity model.
- Make requirement and defect traceability explicit rather than implicit in labels or descriptions.

## Considered options

### Option A: Test Case is a Work Item subtype

This reuses much of Plane's UI but leaks delivery state and issue behavior into the test library. Versioned steps and
immutable execution evidence still require a second model, while upstream Work Item changes become high-conflict.

### Option B: Test Case is an independent project aggregate

This adds domain models and APIs, but gives test assets their correct lifecycle. Typed links connect cases to Plane Work
Items without modifying the Work Item aggregate.

## Decision

Select Option B.

- `TestCase` owns stable project identity, sequence, folder placement, and the current version pointer.
- `TestCaseVersion` is immutable and has a monotonically increasing number unique within a case.
- `TestStep` belongs to exactly one version, has an ordered position, and becomes immutable with that version.
- Editing library content creates a new version in one transaction; it never updates an existing version.
- A future `TestRunCase` pins a `TestCaseVersion`, not merely a `TestCase`.
- Requirement and defect associations use typed link models to Plane `Issue` records.
- Folder placement is library organization and is not duplicated into each version. A run will snapshot presentation
  context where historical reporting requires it.

## Consequences

### Positive

- Historical runs remain reproducible and auditable.
- Test library evolution is independent of Plane issue workflow.
- Fixed and live run semantics can share the same version primitive.

### Negative / accepted trade-offs

- UI and APIs cannot reuse Work Item CRUD directly.
- Version rows increase storage and require explicit pruning policy if attachments become large.
- Cross-project consistency must be enforced in application services in addition to foreign keys.

### Risks and mitigations

- Concurrent edits could allocate the same version -> lock the `TestCase` row and retain a unique database constraint.
- Direct ORM updates could bypass immutability -> reject instance saves after creation and test the invariant.
- Sequence allocation could race -> lock the containing `Project` during case creation and retain a unique constraint.

## Verification

- Unit/model invariant tests: unique case sequence, unique version, immutable version and ordered steps.
- API contract tests: create/list/retrieve/edit-as-new-version/archive and project isolation.
- UI/acceptance tests: an old run continues to render its pinned version after a library edit.
- Migration/rollback verification: clean install and populated Plane database upgrade.

## Architecture diff

Adds Testing domain models and application services inside the Django API container. It adds project-scoped REST
relationships between Web App and API but no new container or trust boundary.
