# ADR 0008: Availability is declared, workspace-wide, and split across projects

- Status: accepted
- Date: 2026-08-06
- Owners: platform
- Related work items/test cases: `plane/tests/unit/availability/`, `plane/tests/contract/app/test_team_calendar.py`
- Supersedes/superseded by: —

## Context

Every schedule this platform produces assumes each person is present every day. `Cycle` carries
`start_date` and `end_date`; nothing anywhere carries "and Ana is out that week, and she is only
half on this project anyway". Grep the backend for `leave`, `holiday`, `absence`, `time_off`,
`availability`, `capacity` or `workload` and the only hits are the license row limit and billing
plans. Upstream Plane has no such domain either, so there is nothing to extend and nothing to
conflict with on the next sync.

The team is **mostly remote and works across several projects at once**. That produces three
distinct questions the platform currently cannot answer, and they are not the same question:

1. **When can we actually talk?** Stated as 「確保找得到人時上線討論」. This is a coordination
   problem across time zones and working hours, and it is the one people hit daily.
2. **Who is out, and when?** The classic leave calendar. Needed, but it is the smaller half.
3. **How is one person's week split across projects?** Stated as 「因為有多個專案所以每個帳號的
   時間和假不知道怎麼呈現和分配比較好」. Without this, every project plans as if it owns 100% of
   everyone, and the sum of all plans exceeds the team several times over.

The requester was explicit that **this is not a monitoring tool**: 「我的目的不是要微管理」. That
constraint is load-bearing, not decoration — it rules out the whole class of designs that would
otherwise be the cheapest way to answer question 1 (presence heartbeats, last-seen, activity
tracking), and it rules out the reports that would otherwise fall out of question 2 for free
(per-person absence histories, utilisation league tables).

Every prior aggregate in this fork is project-scoped. `docs/architecture/testing-platform-workflow.md`
§2 states it as a principle: "Project is the aggregate boundary." All twelve testing models extend
`ProjectBaseModel`. This ADR is the first time that principle does not hold, which is why it needs
writing down rather than assuming.

## Decision drivers

- A person's absence is one fact. Whatever stores it must store it once.
- The calendar has to feed capacity, or it is a wall decoration.
- A remote team's real scarcity is **overlapping hours**, not days. A day-granular model cannot
  answer the question that gets asked most.
- One person on N projects is the normal case here, not an edge case.
- Plane has roles (ADMIN / MEMBER / GUEST) and no reporting line. An approval design that needs a
  manager hierarchy cannot be built here without inventing an org chart nobody asked for.
- Absence reasons are medical often enough that "everyone in the workspace can read them" is not a
  defensible default.
- The fork already decided, in `docs/planning/project-overview-noticeboard.md`, that an editable
  field beside a computed number produces two truths and no owner.

## Decision

### Availability is declared, never observed

The system stores what a person **says** about their availability. It never records, infers or
displays what they actually did.

Concretely, and these are prohibitions on the implementation, not preferences:

- **No presence signal.** No heartbeat, no online/offline dot, no "active now". `User.last_active`
  exists on the model (`plane/db/models/user.py:105`) and this module must never read or surface it.
- **No individual history surface.** There is no "Ana took 12 days this year" screen. This is also
  why the round carries no allowance or balance — a balance is a running total of one person's
  absences, which is the artefact a manager reaches for when the intent drifts.
- **Capacity is forward-looking only.** The cycle panel answers "does this fit", using available
  hours. It never reports hours worked, and it is computed for the cycle, not accumulated per person
  over time.
- **Absence granularity stops at the half-day.** There is deliberately no way to record "out
  14:00–15:30". Finer granularity turns a coordination tool into a timesheet, and the half-day is
  the unit that keeps the arithmetic exact and the calendar drawable.

This is the same move as ADR 0007 — a folder is declared, not inferred — applied to people. Inferred
state about a document is a bug; inferred state about a person is surveillance.

### Reachability is modelled in hours, not days

`MemberWorkProfile` carries a working window (`work_start_time`, `work_end_time`) and an optional
**core window** (`core_hours_start`, `core_hours_end`) — the narrower span a person commits to being
interruptible in. Times are stored naive and interpreted in the member's resolved time zone.

A day-granular model can say Ana is not on leave on Tuesday. It cannot say whether anyone in Taipei
and anyone in Berlin share a single hour that Tuesday, which is the actual question. The core window
exists because "I work 09:00–18:00" and "you can grab me any time in that span" are different
claims, and remote teams that conflate them end up with calendars nobody trusts.

Time zone resolves in order: `MemberWorkProfile.timezone` → `WorkCalendar.timezone` →
`User.user_timezone`. The last already exists and is already maintained
(`plane/db/models/user.py:120`); this module reuses it rather than asking people to state their
location twice.

A half-day absence removes the matching half of the working window, split at its midpoint. That
needs no extra column and keeps the half-day the only granularity anywhere in the model.

### One person's time is allocated across projects, in percent

`MemberProjectAllocation(workspace, member, project, allocation_percent)`, one row per pair,
`clean()` rejecting a member whose allocations sum above 100.

Percent rather than hours because the invariant people need enforced is "this person is not promised
twice", and that is a statement about proportions. Hours are shown, derived from
`hours_per_day × allocation_percent`.

Leave reduces every project the member is allocated to, proportionally — being absent removes you
from everything at once, so a day off costs a 50/50 split member half a day on each project rather
than a full day on one.

**No effective dating in this round.** One current allocation per pair; re-allocating changes what
past cycles compute. The alternative — `effective_from`/`effective_to` with overlap validation — is
real work whose only payoff is retrospective accuracy, and this round's capacity numbers are a
planning input. Recorded here as a known limitation with an obvious upgrade path, rather than
discovered later as a surprise.

### Availability is workspace-scoped

The models take an explicit `workspace` FK on `BaseModel`, following `Initiative` in
`plane/db/models/portfolio.py`, not `ProjectBaseModel`.

Someone on leave is on leave for every project they are a member of. Hanging leave off a project
would store the same Tuesday once per project, and then every read that spans projects — which is
every read questions 1 and 3 need — becomes a de-duplication problem that the schema created and the
application has to solve forever. Worse, the copies can disagree: cancel the leave in one project
and the person is simultaneously present and absent.

`MemberProjectAllocation` and `TeamEvent` carry a `project` FK, because a split and a release day
genuinely do belong to one project. That FK narrows what a row is _about_; it never narrows where
the absence itself lives.

This means project-scoped permission classes do not apply. Availability endpoints use
`WorkspaceEntityPermission`, and cross-workspace isolation must be asserted in `clean()` on every
FK, the same way `plane/db/models/testing.py` asserts same-project.

### Leave and team events are separate tables

They differ in owner (one person / the team), in lifecycle (approval / none), and in cardinality
(one member / many). One table spanning both would be a table where half the columns are null for
half the rows, and where `status = APPROVED` is meaningless on the half that is never approved.

This is the split Azure Boards arrived at too — individual days off and team days off are distinct
concepts there — and it is the shape that lets `TeamEventAttendee` exist without polluting the leave
row with a many-to-many it never uses.

### A working day is computed, never stored

`working_days` is derived on read from the member's calendar. No column caches it.

The alternative is a snapshot column, which drifts the moment an admin adds a public holiday that
falls inside an already-approved leave, and then the product shows two numbers with no way to tell
which is true. Since this round deliberately carries no allowance, nothing reconciles against the
stored figure, so the snapshot would buy nothing and cost a consistency bug.

Accepted trade-off: editing the holiday calendar retroactively changes what an old leave request
"was". For a team-sized deployment with no balances, that is the correct behaviour — the calendar is
the definition of a working day, so changing the definition changes the count.

### Capacity subtracts through an occupancy map, not a sum

For a cycle and a member, build `dict[date, Decimal]` capped at `1.0`, then

```
available_hours(member, project) =
    Σ_d (1 − occupancy[d]) × hours_per_day × allocation_percent/100
    for d in working_days(cycle range)
```

Summing leave hours and event hours independently double-deducts any day carrying both — request a
half-day on the same Wednesday as an all-hands and a naive sum removes 1.5 days of an 8-hour day.
The cap makes that arithmetically impossible rather than something tests have to catch.

Committed work is compared against available hours **only** when the project's estimate system is
`EstimateType.TIME` (`plane/db/models/estimate.py:18`). Story points and hours are not commensurate;
a project estimating in points sees available person-days and a stated reason, not a ratio computed
from two different units.

### The approver is a field, not an org chart

`MemberWorkProfile.approver` is a nullable FK to a user. Null means any workspace ADMIN may decide.

Every comparable product routes a request to the requester's direct manager. Plane has no such
edge — `WorkspaceMember.role` is a flat ADMIN(20) / MEMBER(15) / GUEST(5) enum. Building a reporting
hierarchy to serve one feature would put a second, unowned model of the organisation next to the one
Plane already has. A pointer per member buys the same routing at the cost of one column, and
degrades to "an admin handles it" when nobody sets it.

### A reason is not public

`reason` and `decision_note` serialise only for the leave's own member, its resolved approver, and
workspace admins. Everyone else reads the leave type, the dates and the fact of absence.

Enforced in the serializer, not the client. A field the API returns is public regardless of which
component chooses to render it.

### The service layer exists here

`.agents/skills/plane-qa/references/codebase-map.md` says a service layer with one consumer is
indirection rather than architecture, which is why the delivery surfaces do without one. This module
has four consumers on day one: the app tree, `/api/v1`, the MCP server and the CLI. Business logic
lives in `plane/availability/`, framework-agnostic and `@transaction.atomic`; views are thin
adapters; the public tree subclasses the app views and adds only auth, throttle and error envelope.

### The package is called `availability`

The domain invariant is who is available when; the calendar is one view of it. `plane/calendar/` was
rejected because `calendar` is a Python standard-library module and the collision makes every later
import ambiguous to read. The product surface is still called Team Calendar / 團隊行事曆 — that is a
presentation-layer name and lives in i18n, per guideline A3.

## Consequences

### Positive

- One row per absence, readable from any project without de-duplication.
- The overlap question is answerable at all, which it was not before.
- Capacity numbers move when reality moves, because they read the same rows the calendar draws.
- Over-allocation is detectable — the sum-to-100 rule turns "everyone is on everything" from an
  unpleasant discovery at sprint end into a validation error at assignment time.
- Multi-region teams get correct working-day counts, including Taiwan's 補班日 — a Saturday that
  counts as a working day, which a weekday-mask-only model cannot express at all.

### Negative / accepted trade-offs

- The first non-project aggregate in the fork. Anyone reading `testing-platform-workflow.md` §2 in
  isolation will find an exception; this ADR is the pointer, and the codebase map gains a row.
- Retroactive holiday edits change historical day counts (argued above).
- Allocations are not effective-dated, so a re-split changes what closed cycles compute.
- Half-day granularity only, by design. Someone who genuinely needs "out 14:00–15:30" will put it in
  a team event or say so in chat, and the platform will not know.
- Declared availability can be wrong. Someone who forgets to log a day off will look reachable. The
  alternative is observation, which the requester ruled out and this ADR agrees with.

### Risks and mitigations

- **Capacity double-deduction** → the occupancy cap, plus `test_capacity.py` asserting a same-day
  leave-and-event pair deducts exactly one day.
- **Over-allocation slipping through** → `clean()` on `MemberProjectAllocation` sums the member's
  other rows; contract test asserts 60 + 60 is rejected.
- **Cross-workspace leakage through a shared calendar or leave type** → `clean()` joins every new FK
  to the same-workspace check; contract tests probe a second workspace's IDs.
- **Reason leaking to peers** → contract test reads a colleague's leave as a plain member and asserts
  the field is absent, not merely empty.
- **Time-zone arithmetic drift across DST** → overlap computation converts through `pytz` on real
  dates rather than fixed offsets; `test_overlap.py` covers a DST transition inside the range.
- **A leave type in use being deleted** → `leave_type` is `PROTECT`, and types deactivate via
  `is_active` rather than disappearing.
- **Scope drift into monitoring** → the prohibitions above are testable. A contract test asserts no
  availability response contains `last_active`, and the WBS carries them as a review checklist item.

## Verification

- Unit/model invariant tests: `plane/tests/unit/models/test_availability.py` (day-part validation,
  allocation sum ≤ 100, cross-workspace isolation, soft-delete uniqueness),
  `plane/tests/unit/availability/test_working_days.py` (makeup workdays, month and year boundaries,
  single-day half-days), `test_capacity.py` (occupancy cap, allocation split),
  `test_overlap.py` (multi-zone intersection, DST, half-day window trimming).
- API contract tests: `plane/tests/contract/app/test_team_calendar.py` (CRUD, approval transitions,
  GUEST rejection, reason redaction, no `last_active` in any payload),
  `plane/tests/contract/api/test_team_calendar.py` (`/api/v1` key path, 403/400/409), plus the new
  GETs registered in `test_endpoint_smoke.py`.
- UI/acceptance: store and component specs; manual rehearsal recorded under
  `docs/operations/rehearsals/`. This repository has no Playwright or Cypress and this ADR does not
  claim an automated end-to-end gate.
- Migration/rollback: `0146_team_calendar` is purely additive with no data pass; the reverse drops
  the eight tables and touches nothing upstream owns.

## Architecture diff

- **Added container-internal component**: `plane/availability/` (service layer) alongside
  `plane/testing/`.
- **Added data stores**: `work_calendars`, `calendar_days`, `leave_types`, `member_work_profiles`,
  `member_project_allocations`, `member_leaves`, `team_events`, `team_event_attendees`.
- **Added relationships**: Cycle → availability (read-only, capacity computation); Project →
  `MemberProjectAllocation`; `MemberWorkProfile` → `WorkCalendar`; `MemberLeave` → `LeaveType`;
  MCP/CLI → `/api/v1` availability.
- **Changed trust boundary**: first workspace-scoped aggregate; availability endpoints authorise via
  `WorkspaceEntityPermission` and are closed to GUEST.
- **Unchanged**: every upstream model, every testing model, all existing migrations. `User.last_active`
  remains unread by this module by rule.
