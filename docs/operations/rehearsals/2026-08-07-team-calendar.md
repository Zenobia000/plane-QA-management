# Team calendar rehearsal — 2026-08-07

Scope: the eight-step script in `docs/planning/team-calendar-wbs.md` §6.2, which is the evidence WBS 1.3, 1.7 and
6.2 were waiting on.

## Environment

- Native Django on `:8000` (`apps/api/bin/dev-api.sh`, venv `~/.venvs/plane-qa-api`) against dockerized
  `plane-db` / `plane-redis` / `plane-mq` / `plane-minio`.
- Branch `feat/team-calendar` at `d28024b77` plus this round's work.
- A dedicated workspace `calendar-rehearsal` with four members — Lead (admin), Ana (Taipei), Bob (Berlin),
  Cleo (a third party who is entitled to none of it) — and two projects, Alpha and Beta. Separate from `DEMO`
  on purpose: a rehearsal that mutates data belonging to other work cannot be re-run from a known state.
- Every step went over HTTP to the running server through the app tree the browser uses, with a real session
  cookie obtained from `/auth/sign-in/`. Step 8 repeated four of them through `plane-qa` against `/api/v1`
  with an API key.

**What this is and is not.** This is evidence that the path walks end to end once, against a real server,
with numbers that match arithmetic done by hand. It is not a regression gate — this repo has no Playwright or
Cypress, and §6.2 says so.

## Migrations

Applied to a database already carrying `DEMO` data, then reversed and re-applied, which is the check WBS 2.3,
3.4 and 5.2 name and which pytest (`--nomigrations`) cannot perform:

```
migrate            → 0146_team_calendar, 0147_leave_and_events, 0148_member_allocations   OK
migrate db 0145    → unapplied in reverse order                                            OK
migrate db         → re-applied                                                            OK
```

## The eight steps

| #   | Step                                                        | Result                                                                                                                                                                                                                    |
| --- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Taiwan and Germany calendars; Ana and Bob bound to one each | Both created; both profiles saved with 09:00–18:00 local and distinct core hours                                                                                                                                          |
| 2   | Both members drawn on one axis, zones resolved              | Ana Mon `01:00–10:00Z`, Bob Mon `07:00–16:00Z` — i.e. both 09:00–18:00 at home. No `last_active` anywhere in the payload                                                                                                  |
| 3   | A two-hour window both can make                             | `07:00–10:00Z`, 180 min. By hand: Taipei 01:00–10:00Z ∩ Berlin 07:00–16:00Z = 07:00–10:00Z. Match                                                                                                                         |
| 4   | Ana away 14th–17th August across a make-up Saturday         | 2026-08-15 (a Saturday) marked `makeup_workday`; leave accepted with a half day at the far end; that Saturday still yields Ana working hours                                                                              |
| 5   | The lead decides it; the reason stays private               | Request appears in the lead's queue with `reason` readable; approved; **a second decision returns 409** rather than overwriting the first. Cleo sees that Ana is away and the `reason` key is **absent**, not null        |
| 6   | Allocation refuses to promise Ana twice                     | 50% Alpha + 50% Beta accepted; a further 60% on Alpha refused with `That would allocate this member 110%. One person's allocations must total 100% or less.`                                                              |
| 7   | Cycle capacity drops by the right amount                    | 11 working days (10 weekdays + the make-up Saturday) × 8h × 50% = **44 gross**; away 2.5 days × 8h × 50% = **10 absent**; **34 available**. All three match the server. `committed_comparable: false` on a points project |
| 8   | The same four questions through the CLI                     | `overlap`, `leaves`, `allocations` and `capacity` returned byte-identical figures — same 180-minute window, same 34 available hours, same 100% total — and the over-allocation was refused                                |

## Found during the rehearsal, fixed the same day

The `/api/v1` error envelope in `apps/api/plane/api/views/testing.py` kept the server's message only when it
was a string:

```python
message = raw_message if isinstance(raw_message, str) else "The request could not be completed."
```

Every refusal in this feature comes from `ValidationError.messages`, which is a **list**. So the specific reason
the web UI shows — `That would allocate this member 110%…` — reached the CLI and the MCP server as
`The request could not be completed.` The parameters were equivalent, as WBS 2.12 / 3.11 / 4.9 / 5.9 claim; the
refusals were not.

**Fixed in `ca57a10ac`**, later the same day. `_readable()` joins a list into one sentence and flattens DRF's
field-error dict as `field: message`; the generic line survives only as the last-resort fallback. Contract test:
`test_availability_review_fixes.py` — a model validation message still readable after passing through the
envelope.

The first call was to defer it to its own branch, because the envelope is shared with the testing feature — the
reasoning WBS §1.8 used to leave two upstream 500s alone. That was wrong here, and the difference is worth
keeping: **no test asserted the generic string and nothing read it**, so no existing behaviour depended on it.
Shared code is not automatically off-limits; code somebody relies on is.

## Still found, still not fixed

The two upstream 500s from WBS §1.8 — `workspaces/<slug>/file-assets/` and
`workspaces/<slug>/user-favorite-projects/` — remain open, whitelisted in `KNOWN_WORKSPACE_500` in
`test_endpoint_smoke.py`. Both are upstream registration errors, and nothing in this feature depends on either.

## Commands

```
apps/api/bin/dev-api.sh
manage.py migrate && manage.py migrate db 0145 && manage.py migrate db
plane-qa availability overlap --members ANA,BOB --from 2026-08-03 --to 2026-08-03 --duration 120
plane-qa availability capacity --cycle CYCLE --project ALPHA
```
