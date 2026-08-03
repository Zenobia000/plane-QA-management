# ADR 0005: Project attributes, entity updates and the overview activity feed

- Status: accepted
- Date: 2026-07-31
- Owners: platform
- Related work items/test cases: `docs/planning/enterprise-parity-wbs.md` Phase B (B.1–B.8)
- Supersedes/superseded by: presentation half superseded in part by `docs/planning/project-overview-noticeboard.md` (2026-08-03)

> **Partially superseded.** The schema decisions here stand: `Project.priority`, `start_date` and
> `target_date` remain on the model, and `EntityUpdate` plus the single-table activity feed are
> unchanged and now carry the noticeboard. What no longer holds is the presentation: the Properties
> panel this ADR specified was removed, because putting an editable field beside a computed number
> creates two truths with no owner. The Overview is now a product war room whose derived panels are
> read-only by rule — see the noticeboard spec for the three data classes and the interaction rule
> each implies.

## Context

The Project Overview is the largest backend gap in the enterprise-parity programme. It reports six
things and the schema supports two of them:

| Region                                              | Backing today                                                           |
| --------------------------------------------------- | ----------------------------------------------------------------------- |
| Header: banner, icon, description                   | `Project.cover_image_asset`, `logo_props`, `description_html` — present |
| Progress metrics                                    | Derivable from `Issue` × `State.group` — present                        |
| Properties: state, priority, start and target dates | **absent**                                                              |
| Properties: lead, members                           | `Project.project_lead`, `ProjectMember` — present                       |
| Resource links                                      | **absent**                                                              |
| Status updates                                      | **absent**                                                              |
| Activity feed                                       | **undecided**                                                           |

Three model decisions follow, and each has a cheaper wrong answer that would have been easy to reach
by copying Plane's commercial shape without asking what this fork already has.

## Decision drivers

- The fork already carries a portfolio layer (`plane/db/models/portfolio.py`) with its own status
  vocabulary. A fourth vocabulary would make "planned" mean three slightly different things.
- Updates are wanted on two entities (project, work item) and the official product added the second
  after the first. Building the first as project-only guarantees rework.
- Migrations are the only irreversible part of this programme. Each table added is a table that has to
  be maintained through every upstream rebase.
- `Project` is the single most-serialised model in the codebase; every field added widens dozens of
  payloads.

## Considered options

### Project state: a `ProjectState` table vs. a choices field

**A — a workspace-scoped `ProjectState` model** with groups and ordering, the way `State` works for
work items. Matches the commercial product, which lets an admin define project states per workspace.
Costs a table, a settings surface, a seeding path for existing workspaces, and a default set that
every fixture and test has to know about.

**B — a `TextChoices` field on `Project`**, reusing the vocabulary `Milestone.Status` and
`Initiative.Status` already define. One migration, no settings surface, no seeding. Loses per-workspace
customisation.

`Milestone.Status` and `Initiative.Status` are today byte-identical duplicates of each other. Whichever
option is chosen, that duplication is a defect: three portfolio entities, three copies of one list.

### Updates: one polymorphic model vs. one table per entity

**A — `ProjectUpdate` and `WorkItemUpdate` as separate tables.** Each gets a real foreign key and
straightforward permissions. Two migrations, two serializers, two viewsets, two sets of tests, and the
reaction/threading behaviour written twice.

**B — one `EntityUpdate`**, keyed by entity the way `DeployBoard` already keys polymorphic entities in
this codebase (`entity_identifier` UUID plus `entity_name` with choices). One table, one API shape.
Loses referential integrity on the target: nothing at the database level stops an update pointing at a
deleted work item.

### Activity feed: a new `ProjectActivity` table vs. reusing `IssueActivity`

**A — a `ProjectActivity` model** mirroring `IssueActivity`. Clean naming. The feed then has to merge
two independently-ordered streams under one cursor, which is the expensive part and the part that goes
wrong.

**B — reuse `IssueActivity` with a null `issue`.** `IssueActivity.issue` is _already_ nullable
(`plane/db/models/issue.py:423`) and the model is already a `ProjectBaseModel`, so a project-scoped row
is representable today with no migration at all. One table, one ordering, one cursor, one serializer.
The table name becomes a partial misnomer.

## Decision

**B in all three cases.**

1. `Project` gains `state`, `priority`, `start_date` and `target_date`. `state` uses a new shared
   `PortfolioStatus` extracted from the two identical copies in `portfolio.py`; `Milestone` and
   `Initiative` are repointed at it in the same change, so the vocabulary has exactly one definition.
   `priority` reuses `Issue.PRIORITY_CHOICES` values rather than inventing a parallel scale.

2. One `EntityUpdate` model, a `ProjectBaseModel`, carrying `entity_name` (`project` | `work_item`),
   `entity_identifier`, `status` (`on_track` | `at_risk` | `off_track`), `description`, and a self
   `parent` for replies. Rules implementation must enforce:
   - `entity_identifier` is validated against the named entity _within the request's project_ before
     write. The database cannot enforce it, so the serializer must, and a contract test must prove a
     cross-project identifier is refused.
   - permissions derive from `project`, never from the target entity.

3. The overview activity feed is `IssueActivity` filtered by project. Project-level events are written
   as rows with `issue=None`, which the existing schema already permits.

## Consequences

### Positive

- Three tables' worth of parity delivered by one new table and one `ALTER TABLE`.
- The status vocabulary drops from two definitions to one, and gains its third user rather than a
  third copy.
- Work-item Updates (WBS 3.3 / B.8) needs no further schema — it is the same model with a different
  `entity_name`, which is the outcome the official product arrived at after shipping epic-only updates
  first.
- The activity feed is a single ordered query, so pagination is the one the codebase already has.

### Negative / accepted trade-offs

- No per-workspace project states. If that is wanted later it is a migration from a char column to a
  foreign key, which is more work than starting with the table would have been.
- `EntityUpdate.entity_identifier` has no referential integrity. A deleted work item leaves orphaned
  updates until something reaps them.
- `issue_activities` now stores rows that are not about an issue. The name is wrong and the fix is a
  rename nobody should pay for yet.

### Risks and mitigations

- Orphaned updates after entity deletion → the deleting path removes updates for the entity;
  verified by a contract test that deletes a work item and asserts its updates are gone.
- A caller writing an update against another project's entity → serializer validation scoped to
  `project_id`; verified by a cross-project contract test.
- Widening `Project` payloads breaks a client that pins field sets → the new fields are additive and
  nullable, and the existing project contract tests run unchanged as the regression gate.

## Verification

- Unit/model invariant tests: `PortfolioStatus` shared by all three models; `EntityUpdate` defaults.
- API contract tests: project attribute round-trip; link CRUD scoped to project; update create/list
  for both entity kinds; cross-project identifier refused; updates removed with their entity.
- UI/acceptance tests: overview route renders each region against a seeded project.
- Migration/rollback verification: the migration is additive; `migrate` and reverse both exercised in
  the isolated test stack.

## Architecture diff

- **Added data stores**: `entity_updates`, `project_links`.
- **Changed data stores**: `projects` gains four columns; `milestones` and `initiatives` change the
  source of their status choices without changing stored values.
- **Changed components**: the App API gains project-overview endpoints; `IssueActivity` becomes the
  project activity stream as well as the work-item one.
- **Unchanged**: trust boundaries. Every new endpoint is project-scoped and reuses
  `ProjectEntityPermission`.
