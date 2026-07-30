# Enterprise Feature Parity — Implementation Blueprint

Baseline: this fork's `main` at `fda780985`
Scope: reimplement, in the open, every capability Plane withholds from the Community Edition
Companion documents: `docs/planning/testing-platform-wbs.md`, `docs/architecture/testing-platform-workflow.md`

## Status legend

- `DONE`: implemented and verified in this fork
- `PARTIAL`: some of the stated deliverable ships; the shortfall is named in the row
- `READY`: dependencies satisfied, not started
- `BLOCKED`: missing prerequisite or decision
- `BACKLOG`: not yet ready

---

## 0. What "enterprise" actually means in this codebase

Plane's commercial features are not gated at runtime by a licence check in this repository. They are
gated at **build time**, by a path alias:

```
apps/web/tsconfig.json:9   "@/plane-web/*": ["./ce/*"]
```

In Plane's commercial build the same alias resolves to an `ee/` overlay. The open-source half ships
`apps/web/ce/` — 249 files, of which 86 contain a `return <></>` / `return null` body and 62 are
small enough to be certain no-ops. The gap between the two numbers is real implementations with a
legitimate empty-case early return, several of which this fork already wrote: `issue-identifier.tsx`,
`issue-type-switcher.tsx`, `issue-type-select.tsx` and `additional-properties.tsx` all matched the
pattern and all were already done. **Check a stub before scheduling it.**

With that caveat, the stub set is the precise, machine-checkable list of paid features. It is a
better source of truth than plane.so's pricing page, which describes Cloud tiers and lists as "Free"
several things (initiatives, teamspaces, project overview, worklogs, dashboards, templates) whose code
is not in the open-source repository at all.

Two consequences shape everything below.

**The frontend needs no new wiring.** `apps/web/core` and `apps/web/app` already import 146 distinct
`@/plane-web/...` targets. Every mount point, every prop contract, every store interface already
exists and already compiles. Filling a stub is a local change; nothing upstream of it moves.

**The backend has no such seam.** `apps/api` simply does not contain the paid endpoints or models.
Every family below that needs persistence needs a migration, and migrations are the only part of this
programme that is genuinely irreversible. They are sequenced first within each family for that reason.

### Overlay strategy

Fill the `ce/` stubs in place rather than introducing a parallel `ee/` directory. This fork has already
set that precedent — `ce/components/issues/issue-modal/issue-type-select.tsx` and
`ce/components/issues/issue-details/additional-properties.tsx` are real implementations today, not
stubs. A second overlay would double the upstream-rebase surface without buying isolation, because the
fork has already diverged structurally (the entire Testing platform, `db/models/portfolio.py`,
`db/models/work_item_property.py`).

The cost is real and must be managed: any upstream change to a `ce/` stub becomes a merge conflict.
Mitigation is WBS 0.4 below.

---

## 1. Decisions taken

Recorded 2026-07-31. Each is ADR-worthy; ADR numbers are allocated in WBS 0.2.

### D1 — `/epic-hierarchy/` generalises into a subtree rollup

`apps/api/plane/app/views/issue/epic.py` (256 lines) computes leaf-only rollups — state distribution,
estimate points, requirement coverage, and cycle/module/milestone spread — and serves them from an
Epic-specific endpoint.

The rollup logic is correct and carries QA value upstream Plane does not have: `coverage` is computed
from `requirement_coverage`'s own verdict, so the tree and the release gate cannot disagree. That logic
is kept.

The **endpoint shape** is wrong. Plane's own model makes an Epic an ordinary `Issue` whose
`type.is_epic` is true; hierarchy lives in `parent`. An Epic-only endpoint reinstates the special case
the type system exists to remove, and it means Feature-level or Story-level rollup requires a second
endpoint. Generalise to a subtree rollup any work item can be asked for. Keep `/epic-hierarchy/` as a
thin delegating alias so existing callers — including
`apps/api/plane/tests/contract/app/test_epic_hierarchy.py` and `packages/services/src/epic` — keep
working.

### D2 — the five-level type ladder is retained

The demo seed defines Epic(0) / Feature(1) / Story(2) / Task(3) / Bug(2)
(`apps/api/plane/db/management/commands/seed_ai_software_demo.py:221`). Plane's default is two levels,
Task(0) and Epic(1), but the mechanism is `IssueType.level` and it is depth-agnostic by construction.
Five levels is a configuration of the official model, not a departure from it. The QA traceability and
coverage model already hangs off these levels. No rollback.

The one discipline this imposes is uniform breakdown depth: `epic.py`'s module docstring already
records that leaves at non-uniform depth make denominators incomparable. That is a modelling rule the
platform reports on but cannot enforce, and it stays that way.

### D4 — `IssueType.level` ranks breadth, and the rule forbids inversion rather than requiring descent

Discovered while implementing A.3, and it cuts against upstream in one respect.

**Direction.** This fork seeds Epic 0, Feature 1, Story 2, Task 3, so a _lower_ number is a _broader_
type. Upstream numbers its two defaults the other way (Task 0, Epic 1). The convention kept is this
fork's, because the seeded data and `build_hierarchy`'s root ordering already agree on it and flipping
it would need a data migration to buy nothing.

**Strictness.** The rule is `parent.level <= child.level`, not `<`. A strictly-descending rule reads
tidier and would have rejected data this fork already ships: the demo seed parents a Bug (2) to the
Story (2) it was found in. What has to be refused is the inversion — an Epic filed under a Task —
which is what the official behaviour means when it says hierarchy enforcement "prevents Tasks from
containing Epics".

**Scope.** Untyped work items are exempt. A project with types switched off has every `type` null, and
every tree in such a project predates the rule.

Stated in `apps/api/plane/utils/work_item_hierarchy.py`; enforced on all three paths that write
`parent` (both serializers and the bulk sub-issue endpoint, which writes the column directly).

### D3 — blueprint before code

This document is the deliverable for the current iteration. No feature work starts until the phasing
in section 5 is agreed.

---

## 2. Current state audit

What this fork has already built, independently of upstream:

| Area              | Artefacts                                                                                                                                                                                                                                         | Status                                                                                |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Work Item Types   | `db/models/issue_type.py` (upstream schema: `is_epic`, `level`, `ProjectIssueType`)                                                                                                                                                               | DONE — schema was never gated, only the UI                                            |
| Custom properties | `db/models/work_item_property.py`, `api/{views,urls,serializers}/work_item_property.py`, `packages/services/src/work-item-extensions`, `core/components/work-item-extensions`, `ce/.../issue-type-select.tsx`, `ce/.../additional-properties.tsx` | DONE                                                                                  |
| Portfolio layer   | `db/models/portfolio.py` — `Milestone`, `Initiative`, `InitiativeProject`; `api/views/portfolio.py` CRUD                                                                                                                                          | PARTIAL — REST exists, no web UI, not on `app/urls`                                   |
| Epic hierarchy    | `app/views/issue/epic.py`, `packages/types/src/work-item-hierarchy.ts`, `packages/services/src/work-item-hierarchy`, `app/.../[projectId]/epics/page.tsx`                                                                                         | DONE via Phase A — generalised per D1; create/edit through the shared work-item modal |
| Testing platform  | `db/models/testing.py` and the whole Testing vertical, `packages/qa-sdk`, `apps/plane-qa-cli`, `apps/plane-qa-mcp`                                                                                                                                | DONE — no upstream equivalent at any tier                                             |
| Project overview  | `core/store/theme.store.ts` (`toggleProjectOverviewSidebar`), `core/store/project/project.store.ts` (`ProjectOverviewCollapsible = links \| attachments \| milestones`)                                                                           | PARTIAL — client-side scaffolding only; no route, no models                           |

Everything else in section 4 is unstarted.

---

## 3. Feature family inventory

Eighteen families, derived from the `ce/` stub set. `Size` is a rough order of magnitude for one
implementer: S ≈ days, M ≈ 1–2 weeks, L ≈ 3–4 weeks, XL ≈ 6+ weeks.

### 3.1 Epics

- **Purpose.** A container work item that summarises the work beneath it, so a delivery conversation
  can happen at one level above the task list.
- **Official behaviour.** Not an entity. An `Issue` whose `type.is_epic` is true, at `IssueType.level`
  1 by default. Reached by filtering Work Items on `Type: Epic`; no dedicated sidebar tab. Hierarchy
  enforcement stops a lower-level type from parenting a higher-level one. Progress rolls up from
  descendants. An epic can be converted back to an ordinary work item when scope shrinks.
- **Status.** Closed by Phase A. Hierarchy enforcement, the subtree rollup, the epic modal, the
  epic-scoped store and the type filters all ship; the type switcher was already present.
- **Not done.** Epic-specific analytics (`TEpicAnalytics` in
  `packages/types/src/work-item-hierarchy.ts` is still unreferenced), and the Updates thread, which
  belongs to 3.3 and lands with Phase B.
- **Size.** M — spent.

### 3.2 Project Overview

- **Purpose.** A project landing page that answers "how is this project doing" without opening the
  work-item list — the project-level analogue of what 3.1 does for a subtree.
- **Official behaviour.** Six regions: header with banner/icon and a rich-text goals-and-metrics
  description; resource links; progress metrics broken down backlog/unstarted/started/completed;
  a properties side panel carrying state, priority, lead, members, start and target dates; project
  updates as status posts; and a chronological activity feed.
- **Status.** Closed by Phase B. Attributes, links, updates, progress, activity and the milestones
  panel all ship, in one migration (`0131_project_overview`) and one new page.
- **Not done.** Nothing in the region list. The overview reports and edits all six.
- **Size.** L — spent.

### 3.3 Work Item Updates

- **Purpose.** Threaded status posts on a work item (On Track / At Risk / Off Track) so status is
  reported in-place rather than in a meeting.
- **Official behaviour.** Originally epic-only; now available on every work item type. Shares its shape
  with Project Updates (3.2), which is why the two should share a model.
- **Backend gap.** `EntityUpdate` model keyed by entity type, plus reactions and comments on updates.
- **Frontend gap.** `ce/components/issues/issue-detail-widgets/collapsibles.tsx` and
  `.../action-buttons.tsx` are stubs — this is where the Updates collapsible mounts.
- **Size.** M — but only S if built together with 3.2.

### 3.4 Worklogs and time tracking

- **Purpose.** Record time against a work item; roll it up for billing and capacity.
- **Backend gap.** No worklog model. Note `Project.is_time_tracking_enabled` already exists
  (`db/models/project.py:106`) and is already serialised — the flag is there, the feature is not.
- **Frontend gap.** `ce/components/issues/worklog/property/root.tsx`, `.../activity/root.tsx`,
  `.../activity/worklog-create-button.tsx` are stubs.
- **Mount points.** `@/plane-web/components/issues/worklog/property` (2).
- **Size.** M

### 3.5 Workflows

- **Purpose.** Constrain which state transitions are legal, and require named approvers for some of
  them. This is the single feature most often cited as the reason to pay.
- **Backend gap.** A transition model over `State` with allowed-from/allowed-to and approver sets, plus
  enforcement in the issue-update path. Interacts with 3.5's own drag-and-drop: an illegal board drag
  must be refused server-side, not only hidden client-side.
- **Frontend gap.** The whole `ce/components/workflow/` directory — `state-option.tsx`,
  `use-workflow-drag-n-drop.ts`, `workflow-disabled-message.tsx`, `workflow-disabled-overlay.tsx`,
  `workflow-group-tree.tsx`.
- **Mount points.** `@/plane-web/components/workflow` (10) — the second-most-imported CE target.
- **Size.** L

### 3.6 Templates

- **Purpose.** Create projects and work items from a saved shape instead of from blank.
- **Backend gap.** `Template` model with a typed payload, scoped workspace or project.
- **Frontend gap.** `ce/components/projects/create/template-select.tsx`,
  `ce/components/issues/issue-modal/template-select.tsx`,
  `ce/components/projects/create/attributes.tsx`.
- **Size.** M

### 3.7 Teamspaces

- **Purpose.** A cross-project grouping that owns its own work-item view, pages and members — for an
  org where a team spans projects rather than mapping to one.
- **Backend gap.** A bare `Team` model exists (`db/models/workspace.py`, name/description/workspace/
  logo) and is otherwise unused. Needs `TeamMember`, `TeamProject`, `TeamView`, `TeamPage`, and
  team-scoped issue querying.
- **Frontend gap.** `ce/store/issue/team/*`, `team-project/*`, `team-views/*` (9 files),
  `ce/components/projects/teamspaces/teamspace-list.tsx`,
  `ce/components/workspace/sidebar/teams-sidebar-list.tsx`, three team empty states.
- **Size.** L

### 3.8 Initiatives

- **Purpose.** Workspace-level rollup across epics and projects — the level above a project.
- **Backend gap.** Models exist in this fork (`Initiative`, `InitiativeProject`) with REST CRUD at
  `api/views/portfolio.py`. Missing: status updates, epic membership (only projects link today),
  progress rollup, and `app/urls` exposure for the web client.
- **Frontend gap.** Total. There is no `ce/` stub because CE has no mount point either — the route,
  store and components are all new. `Initiative.Status` choices already exist in the model.
- **Size.** M (given the models) — L including the timeline layout.

### 3.9 Bulk operations

- **Purpose.** Multi-select work items and change properties in one action.
- **Backend gap.** A bulk-update endpoint. `bulk-delete-issues` already exists
  (`app/urls/issue.py:95`); update does not.
- **Frontend gap.** `ce/components/issues/bulk-operations/root.tsx`.
- **Mount points.** `@/plane-web/components/issues/bulk-operations` (3).
- **Size.** S

### 3.10 De-dupe

- **Purpose.** Warn at creation time that a similar work item already exists.
- **Backend gap.** A similarity endpoint over title/description. Postgres trigram is sufficient and
  avoids adding a vector store.
- **Frontend gap.** `ce/components/de-dupe/*` (5 stubs).
- **Size.** M

### 3.11 Cycles, advanced

- **Purpose.** Workspace-wide active-cycle overview, manual cycle end with carry-over, and the cycle
  analytics side panel with burn-down and scope-change charts.
- **Backend gap.** Cycle progress snapshots; transfer-of-incomplete-items on end.
- **Frontend gap.** `ce/components/active-cycles/*`, `ce/components/cycles/end-cycle/modal.tsx`,
  `.../analytics-sidebar/base.tsx`, `.../additional-actions.tsx`. Note
  `app/(projects)/active-cycles/` already exists as a route shell.
- **Size.** M

### 3.12 Gantt dependencies

- **Purpose.** Draw and enforce blocked-by relations on the timeline.
- **Backend gap.** None — `IssueRelation` with `IssueRelationChoices` already models this.
- **Frontend gap.** `ce/components/gantt-chart/dependency/*` (5 stubs),
  `.../layers/additional-layers.tsx`, `ce/store/timeline/base-timeline.store.ts`.
- **Mount points.** `@/plane-web/store/timeline/base-timeline` (5).
- **Size.** M — pure frontend, but drag geometry is fiddly.

### 3.13 Pages, advanced

- **Purpose.** Nested pages, move between projects, per-page sharing and locking, live collaborator
  presence, work-item embeds, AI assist.
- **Backend gap.** Small. `Page.parent`, `Page.is_locked`, `Page.moved_to_page`, `Page.moved_to_project`
  and `PageVersion` all already exist (`db/models/page.py:40-56`). Sharing needs an ACL; the rest is UI.
- **Frontend gap.** 13 stubs across `ce/components/pages/` — `header/{lock,move,share}-control.tsx`,
  `header/collaborators-list.tsx`, `modals/move-page-modal.tsx`, `navigation-pane/*`,
  `editor/ai/*`, `editor/embed/*`, `extra-actions.tsx`.
- **Mount points.** `@/plane-web/components/pages/navigation-pane` (6), `@/plane-web/components/pages` (4).
- **Size.** M — good value per unit of work, since the schema is already there.

### 3.14 Views, advanced

- **Purpose.** Public/private view access control and view publishing.
- **Backend gap.** None. `DeployBoard` already carries a `"view"` entity type
  (`db/models/deploy_board.py:26`), and `IssueView.access` already exists with Private/Public choices
  (`db/models/view.py`). This family is gated purely in the UI.
- **Frontend gap.** `ce/components/views/{publish/modal,access-controller,filters/access-filter,helper}.tsx`.
- **Size.** S

### 3.15 Estimates, advanced

- **Purpose.** Time-denominated estimates alongside points.
- **Backend gap.** `EstimateType` (`db/models/estimate.py:13`) admits only `categories` and `points`.
  Adding `time` is a one-line choices migration plus unit handling on `EstimatePoint`.
- **Frontend gap.** `ce/components/estimates/inputs/time-input.tsx`, `points/delete.tsx`,
  `update/modal.tsx`, `estimate-list-item-buttons.tsx`.
- **Size.** S

### 3.16 Intake, advanced

- **Purpose.** Accept work from outside the workspace by email or public form, not only in-app.
- **Backend gap.** Inbound email ingestion and a form endpoint. `Intake`/`IntakeIssue` models exist;
  `IntakeIssue.source` needs to become meaningful.
- **Frontend gap.** `ce/components/inbox/source-pill.tsx`,
  `ce/components/projects/settings/intake/header.tsx`.
- **Size.** L — inbound email is operational surface, not just code.

### 3.17 Dashboards and advanced analytics

- **Purpose.** Composable widgets over workspace data.
- **Backend gap.** `Dashboard` and `Widget` models plus an aggregation API. `AnalyticView` exists but
  is a different, older concept.
- **Frontend gap.** `ce/components/analytics/{tabs,use-analytics-tabs}.tsx`, `ce/store/analytics.store.ts`.
- **Size.** L

### 3.18 Remaining surface

Grouped because none justifies its own family:

| Item                          | CE stub                                                       | Note                                                                 |
| ----------------------------- | ------------------------------------------------------------- | -------------------------------------------------------------------- |
| App rail / multi-app switcher | `ce/components/app-rail/*`, `*/app-switcher.tsx`              | Only meaningful once Wiki or Drive exists                            |
| Automations                   | `ce/components/automations/root.tsx`                          | Rule engine; depends on 3.5                                          |
| Relations, extended           | `ce/components/relations/*`                                   | 7 mount points                                                       |
| Power-K, extended context     | `ce/components/command-palette/power-k/*`                     | Depends on whichever families ship                                   |
| Member activity / audit       | `ce/components/workspace/members/members-activity-button.tsx` | Needs an audit log model                                             |
| Work-item identifier badge    | `ce/components/issues/issue-details/issue-identifier.tsx`     | 21 mount points — the single most-imported stub, and trivially small |
| Customers                     | no stub                                                       | Business-tier concept; no CE mount point exists                      |
| Recurring work items          | no stub                                                       | Needs a scheduler                                                    |
| Wiki                          | no stub                                                       | Workspace-level page tree; large                                     |

---

## 4. Programme governance

| WBS | Work package                       | Depends on | Deliverable / acceptance                                                                           | Tests                                       | Status                      |
| --- | ---------------------------------- | ---------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------- | --------------------------- |
| 0.1 | Pin the CE↔EE seam                 | —          | This document, section 0; alias and stub inventory recorded                                        | `grep -c` reproduces the stub count         | DONE                        |
| 0.2 | ADRs for the programme's decisions | 0.1        | ADR 0005 accepted (Phase B model shape). D1–D4 are recorded in section 1 and still want ADR files  | ADR review                                  | PARTIAL                     |
| 0.3 | Feature-family inventory           | 0.1        | Section 3; every family has backend gap, frontend gap and mount points                             | Documentation review                        | DONE                        |
| 0.4 | Fork-divergence policy             | 0.1        | Written rule for reconciling upstream changes to filled `ce/` stubs; recorded in `CONTRIBUTING.md` | Rebase rehearsal against upstream `preview` | READY                       |
| 0.5 | Phasing agreed                     | 0.3        | Section 5 signed off                                                                               | —                                           | BLOCKED — awaiting decision |

---

## 5. Proposed phasing

Sequenced by dependency and by value per unit of irreversible schema change.

### Phase A — converge what exists (no new schema)

Pays down D1 and turns the two half-built families into whole ones. Nothing here needs a migration.

| WBS | Work package               | Depends on | Deliverable / acceptance                                                                                                                   | Tests                                                                                | Status |
| --- | -------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------ | ------ |
| A.1 | Subtree rollup endpoint    | 0.2        | `WorkItemHierarchyEndpoint` answers for any work item; `/epic-hierarchy/` and `/work-item-hierarchy/` are the same view with no root named | `test_epic_hierarchy.py`, 11 cases incl. subtree, leaf, defect-absent, cross-project | DONE   |
| A.2 | Rollup service and types   | A.1        | `WorkItemHierarchyService.getProjectHierarchy`/`getSubtree`; `TWorkItem*` types with deprecated `TEpic*` aliases                           | `tsc --noEmit` on web                                                                | DONE   |
| A.3 | Hierarchy enforcement      | 0.2        | Inversion refused on both serializers and the bulk sub-issue endpoint, per D4                                                              | `test_work_item_hierarchy_rules.py`, 7 cases                                         | DONE   |
| A.4 | Epic create/edit modal     | 3.1        | `CreateUpdateEpicModal` is `CreateUpdateIssueModal` with the epic type preloaded, not a parallel form                                      | Type check                                                                           | DONE   |
| A.5 | Epic store                 | A.4        | `ProjectEpicsFilter` injects `epic: true`; backend gains `issue_type` and `epic` filters                                                   | `test_work_item_type_filters.py`, 7 cases                                            | DONE   |
| A.6 | Type switcher              | A.3        | Already implemented in this fork; the A.3 rule now guards the conversions it offers                                                        | Covered by A.3                                                                       | DONE   |
| A.7 | Work-item identifier badge | —          | Already implemented in this fork; the stub detector counted its empty-case early return                                                    | —                                                                                    | DONE   |

Exit gate: an epic can be created, converted and rolled up through the ordinary work-item surface, and
the Epics page is one view of that rather than a separate mechanism.

Exit evidence: 605 API tests and 36 web tests pass; `apps/web` type-checks clean.

**A.5 turned up a live bug rather than a missing feature.** `issue_type` has always been a valid
`TIssueParams` and the frontend has always sent it, but `ISSUE_FILTER` in
`apps/api/plane/utils/issue_filters.py` had no handler for it, so the parameter was accepted into the
query string and silently dropped — filtering a work-item list by Epic returned everything. `epic` is
the new companion: the epics list has to select by the `is_epic` flag because it has no way to know
which type id carries it in a given workspace. Only the positive direction exists; `epic=false` would
need `type IS NULL OR is_epic = false`, an OR that a kwargs dict returned for `.filter(**filters)`
cannot carry, and one that silently dropped untyped items would be worse than its absence.

### Phase B — Project Overview and Updates

The two families that share a model, done together. First migrations of the programme.

| WBS  | Work package                        | Depends on | Deliverable / acceptance                                                                                                                   | Tests                         | Status |
| ---- | ----------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------- | ------ |
| B.1  | ADR: project attributes and updates | A.7        | ADR 0005 accepted: choices field over a `ProjectState` table, one `EntityUpdate` over two tables, `IssueActivity` reused over a new stream | ADR review                    | DONE   |
| B.2  | Project attribute migration         | B.1        | `state`, `priority`, `start_date`, `target_date` on `Project`; `PortfolioStatus` extracted so the vocabulary has one definition            | Contract tests, 3 cases       | DONE   |
| B.3  | `ProjectLink` model and API         | B.2        | Project-scoped CRUD, shaped after `ModuleLink`                                                                                             | Contract tests, 2 cases       | DONE   |
| B.4  | `EntityUpdate` model and API        | B.1        | Status posts on project and work item from one model; target validated in-project; updates reaped with their entity                        | Contract tests, 5 cases       | DONE   |
| B.5  | Project activity stream             | B.2        | `IssueActivity` filtered by project, no new table                                                                                          | Covered by the overview cases | DONE   |
| B.6  | Overview route and layout           | B.2–B.5    | `/projects/:projectId/overview` with banner, icon, progress, properties, links, updates, activity; sidebar entry at sortOrder 0            | `tsc`, web suite              | DONE   |
| B.7  | Milestones on the overview          | B.6        | `Milestone` surfaces with per-milestone done/total counts                                                                                  | Contract test                 | DONE   |
| B.8  | Work-item Updates widget            | B.4        | `issue-detail-widgets/collapsibles.tsx` renders the same `UpdatesPanel` with `entity_name=work_item`, replies included                     | `tsc`                         | DONE   |
| B.9  | Update replies                      | B.4        | The list is the top of the thread; `?parent=<id>` fetches one update's replies, loaded on expand                                           | Contract tests, 2 cases       | DONE   |
| B.10 | Banner and icon editing             | B.6        | The create form's two pickers, reused over the existing `cover_image_asset` and `logo_props`. No migration                                 | `tsc`                         | DONE   |
| B.11 | Locale coverage                     | B.6        | `sidebar.overview` translated in all 19 locales per the `translate` skill, not left as an English fill                                     | `check:sync`                  | DONE   |

Exit gate: a project has a landing page that reports its own health, and status updates exist at both
project and work-item level from one model.

Exit evidence: 622 API tests and 36 web tests pass; `apps/web` type-checks clean; `check:lint` reports
no errors; migration `0131_project_overview` is additive throughout; all 19 locales in sync.

**Two traps worth recording, both found by tests rather than by reading.**

_Two aggregates over one multi-valued relation cross-join._ Annotating `Milestone` with an unfiltered
`Count("work_items")` and a filtered one made Django reuse a join for the first and add a second for
the other, reporting one-of-two-done as two-of-two. Both milestone counts and the project progress bar
therefore group in a single pass and total in Python, which is also what
`plane/app/views/issue/epic.py` already does.

_`Issue.save()` back-fills a missing state from the project._ A fixture that created a work item with
no state in a project whose only state was "Done" produced a silently complete item. Test data has to
name states explicitly.

### Phase C — cheap wins

Families whose schema already exists. Highest ratio of visible capability to risk.

C.1 confirmed the premise: the whole of view access control was one `read_only` entry on a
serializer, and publishing was one endpoint that names an entity type `DeployBoard` already
carried. No migration, 5 contract tests, and the four `ce/` stubs filled against their existing
prop contracts.

| WBS | Work package                       | Depends on | Deliverable / acceptance                                                                                                                | Tests                      | Status |
| --- | ---------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- | ------ |
| C.1 | Views access control and publish   | —          | `IssueView.access` made writable and surfaced; `ProjectViewPublishEndpoint` over the existing `DeployBoard` `"view"` type. No migration | Contract tests, 5 cases    | DONE   |
| C.2 | Pages: lock, move, share           | —          | Three header controls over existing `Page` fields                                                                                       | Contract + component tests | READY  |
| C.3 | Pages: nesting and navigation pane | C.2        | Page tree over existing `Page.parent`                                                                                                   | Component tests            | READY  |
| C.4 | Bulk operations                    | —          | Bulk-update endpoint; multi-select toolbar                                                                                              | Contract + component tests | READY  |
| C.5 | Gantt dependencies                 | —          | Draw and persist blocked-by over existing `IssueRelation`                                                                               | Component tests            | READY  |
| C.6 | Estimates: time input              | —          | Time-denominated estimate type                                                                                                          | Unit tests                 | READY  |

### Phase D — the hard families

Each needs its own ADR and its own schema. Sequence by what the fork actually needs; not all may be
wanted.

| WBS  | Work package              | Depends on | Size | Status  |
| ---- | ------------------------- | ---------- | ---- | ------- |
| D.1  | Workflows and approvals   | A.3        | L    | BACKLOG |
| D.2  | Teamspaces                | —          | L    | BACKLOG |
| D.3  | Templates                 | B.2        | M    | BACKLOG |
| D.4  | Worklogs                  | —          | M    | BACKLOG |
| D.5  | Initiatives UI and rollup | A.1, B.4   | M    | BACKLOG |
| D.6  | Cycles, advanced          | —          | M    | BACKLOG |
| D.7  | De-dupe                   | —          | M    | BACKLOG |
| D.8  | Dashboards                | —          | L    | BACKLOG |
| D.9  | Intake email and forms    | —          | L    | BACKLOG |
| D.10 | Automations               | D.1        | L    | BACKLOG |

---

## 6. Risks

| Risk                                           | Consequence                                                                                  | Mitigation                                                                                                           |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Filled `ce/` stubs conflict on upstream rebase | Merge cost grows with every family shipped                                                   | WBS 0.4: written reconciliation policy plus a rehearsed rebase before each phase                                     |
| Migration ordering across parallel families    | `apps/api` migration graph forks; `0130_project_view_axes_on_by_default` is the current head | One family in flight per migration at a time; rejoin the graph before merging, as `6c2067e7b` already had to do once |
| Non-uniform breakdown depth                    | Rollup denominators stop being comparable                                                    | Already documented in `epic.py`; surface it as a warning in the UI rather than silently reporting a wrong ratio      |
| Scope drift into Wiki, Drive, AI               | Programme never converges                                                                    | Section 3.18 items stay out of scope until a phase explicitly admits them                                            |
| i18n debt                                      | 19 locales in `packages/i18n/src/locales`; new strings land English-only                     | Follow the `translate` skill per phase, not at the end                                                               |

---

## 7. Documentation obligations

Per the repository's code↔docs synchronisation rule, each phase must update:

- this document's Status column — it is the single source of truth for the programme
- `docs/architecture/` when a family introduces a new aggregate or crosses an existing boundary
- `docs/architecture/decisions/` for every ADR-worthy choice named above
- `.env.example` if a family introduces configuration (3.16 will)
- `docs/api/` when an endpoint is added or its shape changes
