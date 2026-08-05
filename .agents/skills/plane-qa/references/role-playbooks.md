# Plane QA — role playbooks (PM & QA)

This system merges JIRA-style project management with QA test management in one project scope. When a user asks you to act for a role ("幫我排這個 sprint"、"幫這個需求建測試"), follow the matching playbook. Steps reference CLI commands (MCP tools map 1:1; see tooling.md); planning endpoints not wrapped by the CLI use raw REST with `X-API-Key` under `/api/v1/workspaces/{slug}/projects/{project_uuid}/`.

## Shared vocabulary

| Concept                   | Plane entity                                                                                                                                                                                 | Owned by                     |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| Product area / capability | **Module** — a grouping of work items by what part of the product they build                                                                                                                 | PM                           |
| Epic                      | **Work item typed `Epic`** (`IssueType.is_epic`, level 0). The `/epics` page is the work-item list plus that predicate, not the modules list                                                 | PM                           |
| Sprint / time-box         | **Cycle** (has `start_date`, `end_date`)                                                                                                                                                     | PM                           |
| Requirement / task / bug  | **Work item (Issue)** — `state`, `priority`, `start_date`, `target_date`, `assignees`, `labels`, `requirement_kind`; broken down by `type` (Epic 0 → Feature 1 → Story 2 → Task 3; Bug at 2) | PM                           |
| Acceptance contract       | **Test case** linked to the requirement work item                                                                                                                                            | QA                           |
| Execution evidence        | **Test run** (may be scoped to a cycle/module) + append-only results                                                                                                                         | QA                           |
| Bug found by testing      | **Defect** = Issue auto-created from a failed/blocked result, atomically linked                                                                                                              | QA creates → PM/dev resolves |
| Ship decision             | **Release gate** (`quality release-gate`)                                                                                                                                                    | PM+QA together               |

The link chain that makes everything traceable: `Module → Work item ↔ Test case → Run(cycle) → Result → Defect(Issue)`. Never break it by working across projects.

Two things about the work-item half are easy to get wrong, and both have already cost this codebase a repair command:

- **A work item's breakdown level and its requirement nature are different axes.** `type` (with `level`) says how wide the item is; `requirement_kind` (`functional` / `quality` / `none`) says what kind of promise it makes. A quality requirement is a Story with `requirement_kind: quality` — not a type of its own, and not a custom property.
- **The acceptance contract attaches at Story level**, where acceptance is actually decided. Coverage rolls up, so a Feature or Epic reports the contracts beneath it; only types marked `needs_acceptance` (Epic/Feature/Story by default, not Task/Bug) get a coverage row at all.

## PM playbook — schedule & issue planning

Goal: turn requirements into scheduled, assigned, traceable work items.

### 1. Resolve context (always first)

```bash
plane-qa project get && plane-qa project states   # state UUIDs — never invent states
```

### 2. Build structure — module per capability, cycle per time-box (raw REST)

```bash
curl -sS -H "X-API-Key: $PLANE_API_KEY" -H "Content-Type: application/json" \
  -X POST "$PLANE_URL/api/v1/workspaces/$PLANE_WORKSPACE/projects/<project_uuid>/modules/" \
  -d '{"name":"Checkout v2"}'
curl -sS -H "X-API-Key: $PLANE_API_KEY" -H "Content-Type: application/json" \
  -X POST "$PLANE_URL/api/v1/workspaces/$PLANE_WORKSPACE/projects/<project_uuid>/cycles/" \
  -d '{"name":"Sprint 2026-08A","start_date":"2026-08-03","end_date":"2026-08-14"}'
```

Other planning endpoints (all GET/POST at collection, GET/PATCH/DELETE at `/{uuid}/`): `cycles/`, `modules/`, `labels/`, `members/`. Membership: `POST cycles/{cycle_uuid}/cycle-issues/` and `POST modules/{module_uuid}/module-issues/` with `{"issues":["<issue_uuid>", ...]}`. Sprint rollover: `POST cycles/{cycle_uuid}/transfer-issues/` with `{"new_cycle_id":"..."}` — moves **only incomplete** work items and snapshots the old cycle's progress; completed items stay behind.

Finding a member's UUID: `GET members/` returns `[{id, member, role}]` — **use `member` (the user UUID) for `assignees`, not `id`** (`id` is the membership row). Note the public REST tree calls issues `work-items/`; CLI/MCP call the same entities `issue*`.

### 3. Create scheduled work items

CLI flags cover name/state/priority/description; put scheduling fields in `--body` (spread into the payload verbatim):

```bash
plane-qa type list                        # resolve type UUIDs; do not invent a new vocabulary
plane-qa issue create --name "Support Visa 3DS" --priority high \
  --body '{"type_id":"<story_type_uuid>","parent":"<feature_uuid>","requirement_kind":"functional",
           "start_date":"2026-08-03","target_date":"2026-08-07",
           "assignees":["<member_uuid>"],"labels":["<label_uuid>"]}'
```

Constraints: `start_date` ≤ `target_date` (400 otherwise); assignees must be project members; dates are `YYYY-MM-DD`. A parent may not be a narrower type than its child — `IssueType.level` is Epic 0 → Feature 1 → Story 2 (Bug 2) → Task 3, lower is broader, and an inverted parent is a 400 naming both types. Then attach to cycle/module via the REST membership endpoints above.

### 4. Definition of Ready — the PM↔QA handshake

A requirement is not ready for implementation until QA has linked at least one acceptance test case (including one unhappy path). `plane-qa quality coverage` proves a case is linked; the unhappy-path check is not automated — inspect `plane-qa case list --issue-id <uuid>` (convention: tag negative cases `--tags negative` at creation so this check is greppable). An uncovered requirement in scope is a planning gap: ask QA (or run the QA playbook) before scheduling implementation.

### 5. Track and steer

- Move states: `plane-qa issue transition --issue QA-34 --state-id <uuid>`; record decisions: `issue comment`.
- Scope views: `plane-qa issue list --state <uuid> --priority urgent`; cycle progress via `GET cycles/{uuid}/` (progress counts) or `cycle-issues/`.
- Defects arrive as high-priority Issues created by QA/CI with a full evidence description — treat them as normal work items to schedule and resolve; never edit the underlying test result.

### 6. Release review

`plane-qa quality release-gate` is the ship/no-ship input: `ready` needs a latest run with zero failed/blocked/open cases and zero open defects. Report blockers item-by-item; unfinished scope rolls to the next cycle via `transfer-issues`.

## QA playbook — test flow design & execution

Goal: an acceptance contract per requirement, and an unbroken evidence chain per build.

### 1. Intake

```bash
plane-qa issue list --per-page 50          # requirements in scope
plane-qa quality coverage                  # which requirements lack test cases
```

### 2. Design the library — folder per feature area, case per acceptance criterion

```bash
plane-qa folder create --name "Checkout"
plane-qa case create --title "Visa 3DS challenge succeeds" --folder-id <folder> --priority high \
  --preconditions '{"text":"Test card enrolled in 3DS"}' \
  --steps '[{"action":{"text":"Pay with enrolled Visa"},"expected_result":{"text":"3DS challenge shown"}},
            {"action":{"text":"Complete challenge"},"expected_result":{"text":"Order confirmed"}}]'
plane-qa case link-issue --case <case_uuid> --issue QA-34    # ← the traceability step; never skip
```

Per requirement create at least one happy-path and one unhappy-path case (DoR demands it). Editing a case later publishes a new immutable version; historical runs keep the version they pinned.

### 3. Plan execution per sprint/build — scope the run to the PM's cycle

```bash
plane-qa case list --issue-id <requirement_uuid>             # collect case ids in scope
plane-qa run create --name "Sprint 2026-08A regression" --build "$GIT_SHA" \
  --cases <c1>,<c2>,<c3> --body '{"cycle_id":"<cycle_uuid>"}'  # module_id also accepted
```

### 4. Execute → defect → retest (evidence chain)

```bash
plane-qa run record-result --run <run> --run-case <rc> --status failed --actual '{"text":"3DS iframe blank"}'
plane-qa run create-defect --run <run> --run-case <rc> --result <result_id>   # only from failed/blocked
# → high-priority Issue lands in the PM's backlog with auto-built evidence; comment/assign it as needed
#   a defect counts as "open" for the release gate until its state's GROUP is completed or cancelled
#   (check the "group" field in `plane-qa project states` output)
# after the fix: retest APPENDS — the failure stays on record
plane-qa run record-result --run <run> --run-case <rc> --status passed
```

If a recorded failure turns out to be a false alarm: results can never be edited or deleted. Re-execute and append a new result whose `--actual` states the misjudgment (e.g. `{"text":"False alarm: env misconfig, re-verified"}`), and close the defect through its issue states. Never append a `passed` result without actually re-checking the behavior.

### 5. Close and report

```bash
plane-qa quality overview && plane-qa quality release-gate
plane-qa run close --run <run> --yes     # only after explicit confirmation; closed runs reject results
```

Report per-requirement coverage status, failures, and open defects — never "all good" from a single number.

### 6. Automation lane (CI)

Pre-link CI tests to library cases by uploading once with `test_case_id` per result, or rely on stable `external_id`s (JUnit: `classname::name`) — after the first upload the mapping persists; unmapped results auto-create cases tagged `automated` (review these and file them into folders + link requirements, or they stay orphaned). Idempotency-key recipe and retry semantics: see workflows.md §3.

## Product playbook — the field-to-engineering path

Goal: a complaint that arrives from a customer reaches the backlog attributed, triaged, and visible to whoever decides what ships.

The Project Overview assembles this as a war room — release readiness, progress, the noticeboard, intake grouped by customer, the overdue/urgent shortlist. **You cannot read it.** It is session-auth only (see api-reference.md). What you can do is supply everything it reads, over `/api/v1`.

### 1. Learn this project's vocabulary before writing

```bash
curl -sS -H "X-API-Key: $PLANE_API_KEY" \
  "$PLANE_URL/api/v1/workspaces/$PLANE_WORKSPACE/projects/<project_uuid>/work-item-properties/"
```

Find the property with `is_grouping_dimension: true` — that is what the frontline panel groups by, and its `name` is whatever this team calls the axis (customer, tenant, region, pilot cohort). If none is marked the panel is off, and marking one is a human decision in settings, not yours to flip so your output renders.

### 2. File what the field reported

```bash
curl -sS -H "X-API-Key: $PLANE_API_KEY" -H "Content-Type: application/json" \
  -X POST "$PLANE_URL/api/v1/workspaces/$PLANE_WORKSPACE/projects/<project_uuid>/intake-issues/" \
  -d '{"issue":{"name":"Export times out past 5,000 rows","description_html":"<p>Blocks month-end close.</p>"}}'
```

Intake is the right home for anything originating outside the team; it lands as `pending` and stays out of the sprint until a human accepts it. Do not create it as an ordinary work item to "save a step" — that skips the triage decision the panel exists to surface.

### 3. Attribute it, or it lands in the untagged pile

```bash
curl -sS -H "X-API-Key: $PLANE_API_KEY" -H "Content-Type: application/json" \
  -X PUT "$PLANE_URL/api/v1/workspaces/$PLANE_WORKSPACE/projects/<project_uuid>/work-items/<issue_uuid>/properties/<dimension_uuid>/" \
  -d '{"value":["acme"]}'
```

`value` is a list for a multi-select, and a report affecting two accounts should carry both — the panel shows it under each, which is the honest rendering. Unattributed intake is not dropped; it is grouped last as the measure of what nobody has claimed. Leaving your own writes there makes that number lie.

### 4. Leave triage to a human

Retriage is `PATCH intake-issues/{issue_uuid}/` with `{"status": 1}` (accepted) or `-1` (rejected), **ADMIN only, keyed by the work item's id**. Accepting means "this is going into the plan" — a scheduling commitment. Propose it; do not perform it unless the user asked for exactly that.

### 5. What you cannot do

Post to the noticeboard. `updates/` has no API-key route. If the user wants an announcement made, write the text and tell them where to paste it.

## Role decision guide

| The user asks for…                                  | Playbook         | Key commands                                                           |
| --------------------------------------------------- | ---------------- | ---------------------------------------------------------------------- |
| Sprint/schedule setup, backlog grooming, assignment | PM §2–3          | REST cycles/modules + `issue create --body`                            |
| "Is this requirement ready to build?"               | PM §4            | `quality coverage`                                                     |
| Status report / ship decision                       | PM §6            | `quality release-gate`                                                 |
| "Write/organize tests for X"                        | QA §2            | `folder/case create`, `case link-issue`                                |
| "Run the tests for this sprint/build"               | QA §3–5          | `run create --body cycle_id`, `record-result`                          |
| "CI should report results here"                     | QA §6            | `automation upload-*`                                                  |
| Bug triage from test failures                       | QA §4 then PM §5 | `create-defect`, `issue transition`                                    |
| "A customer reported X" / field escalation          | Product §2–3     | `intake-issues/` + property `PUT`                                      |
| "Which customers are blocked?"                      | Product §1       | read properties + `intake-issues/`; the assembled view is browser-only |

One agent may play several roles in a session — but keep the handshakes explicit: DoR check before scheduling implementation, defect → resolve → retest before closing a run, release gate before claiming shippable, and attribution before a field report counts as triaged.
