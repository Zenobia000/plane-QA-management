# Team calendar API

Workspace-scoped, unlike the rest of this fork's surfaces. The reasoning is in
[ADR 0008](../architecture/decisions/0008-availability-is-a-workspace-fact.md): an absence
is a fact about a person, so it is stored once per person, not once per project.

Two trees, same handlers:

| Tree   | Prefix                        | Auth           |
| ------ | ----------------------------- | -------------- |
| App    | `/api/workspaces/<slug>/…`    | Session cookie |
| Public | `/api/v1/workspaces/<slug>/…` | `X-API-Key`    |

The public tree is thin subclasses — same behaviour, plus throttling, an `X-Request-ID`
header on every response, and errors wrapped in the standard envelope.

## Authorisation

`WorkspaceAvailabilityPermission`: an **active workspace member with role ADMIN or MEMBER**.

**GUEST is refused, including on reads.** This is the only workspace surface in the fork
that closes to guests. A guest is someone let into one project; this is the whole team's
working hours.

Narrower rules per endpoint:

- Creating a work calendar: ADMIN.
- Writing a member's work profile: that member, or ADMIN.

## What this API will never return

Availability is **declared, never observed**. No endpoint here exposes `User.last_active`,
`last_login`, or any other signal of what someone actually did. Contract tests assert the
absence of those fields rather than trusting the implementation to keep leaving them out.

There is also no per-person history endpoint and no leave balance — see ADR 0008 for why
those are absent by decision rather than by omission.

## Instants

Every window is an absolute UTC ISO-8601 pair. Local wall-clock times appear only on a
member's own profile (`work_start_time` etc.), where they are read in that member's own
zone. `"Tuesday 09:00"` is not a comparable quantity across two cities, and comparing across
cities is what this surface is for.

Time zone for a member resolves in this order:

1. `MemberWorkProfile.timezone`
2. the member's `WorkCalendar.timezone`
3. `User.user_timezone` (already maintained by Plane)

---

## `GET …/availability/capabilities/`

Which slices are live. Every flag is `false` until the slice implementing it ships, and the
client renders an empty state for each `false`.

```json
{
  "enabled": true,
  "stage": "reachable-hours",
  "capabilities": {
    "schedule": true,
    "overlap": true,
    "leave": false,
    "allocation": false,
    "capacity": false
  }
}
```

## `GET …/availability/schedule/`

Declared windows for every member (or a named subset) over a date range.

| Query        | Required | Notes                                          |
| ------------ | -------- | ---------------------------------------------- |
| `from`       | yes      | `YYYY-MM-DD`                                   |
| `to`         | yes      | `YYYY-MM-DD`, at most 366 days after `from`    |
| `member_ids` | no       | Comma-separated. Omit for the whole workspace. |

```json
{
  "from": "2026-08-03",
  "to": "2026-08-09",
  "members": [
    {
      "member_id": "…",
      "timezone": "Asia/Taipei",
      "calendar_id": "…",
      "hours_per_day": 8.0,
      "working": [{ "start": "2026-08-03T01:00:00+00:00", "end": "2026-08-03T10:00:00+00:00", "minutes": 540 }],
      "core": [{ "start": "2026-08-03T06:00:00+00:00", "end": "2026-08-03T09:00:00+00:00", "minutes": 180 }]
    }
  ]
}
```

A member who has declared nothing appears with empty `working` and `core`. They are **not**
given an invented 09:00–18:00: that would put a claim on screen the person never made, and
colleagues would plan around it.

`400` on a missing, inverted, malformed or over-wide range.

## `POST …/availability/overlap/`

When a named group is reachable at once. A POST for a read, because the member list is the
request and a query string of twenty UUIDs is neither readable nor reliably deliverable.
Nothing is written.

```json
{
  "member_ids": ["…", "…"],
  "date_from": "2026-08-03",
  "date_to": "2026-08-09",
  "duration_minutes": 60
}
```

```json
{
  "duration_minutes": 60,
  "core": [{ "start": "…", "end": "…", "minutes": 180 }],
  "working": [{ "start": "…", "end": "…", "minutes": 180 }],
  "unknown_members": [],
  "members_without_hours": ["…"]
}
```

**`core` and `working` are separate lists on purpose.** They answer different questions —
"when may I interrupt everyone" versus "when is everyone merely at work" — and merging them
promotes the second into the first. Prefer `core`.

A member with no core window contributes their working window to the `core` calculation:
they have not asked to be protected, so they are not the constraint.

`members_without_hours` names anyone who has declared nothing. Without it, an empty result
reads as "never", when the truth is "somebody has not said yet".

## `GET | POST …/availability/calendars/`

List, or create (ADMIN only), a regional work calendar.

```json
{
  "name": "Taiwan",
  "timezone": "Asia/Taipei",
  "working_weekdays": [1, 2, 3, 4, 5],
  "is_default": true
}
```

`working_weekdays` is ISO — Monday is 1. Setting `is_default` demotes the incumbent in the
same transaction, so "make this the default" cannot half-succeed.

Individual dates that override the weekday rule (`kind` is `holiday` or `makeup_workday`)
are written through the service layer; `makeup_workday` exists for Taiwan's practice of
working a Saturday to bridge a long weekend, which a weekday-mask-plus-holidays model
cannot express at all.

## `GET …/availability/profiles/` · `GET | PATCH …/availability/profiles/<member_id>/`

Read is open to any workspace member — seeing when a colleague is reachable is the point.
Write is that member or an ADMIN: a declaration somebody else made on your behalf is not a
declaration.

```json
{
  "work_calendar": "…",
  "timezone": "Asia/Taipei",
  "work_start_time": "09:00",
  "work_end_time": "18:00",
  "core_hours_start": "14:00",
  "core_hours_end": "17:00",
  "hours_per_day": "8.00",
  "approver": "…",
  "clear_core_hours": false
}
```

Every field is optional; an omitted field is left unchanged. `clear_core_hours` therefore
exists as the only way to withdraw a core-hours commitment once made.

Rejected with `400`:

- a working day that ends before it starts
- core hours outside the working window, or only one half supplied
- `hours_per_day` outside `(0, 24]`
- a calendar or approver belonging to a different workspace

A member with no profile reads as `{"member": "…", "declared": false}` with `200`, not a
`404`. Having declared nothing is a state, not an error.

## `GET | POST …/availability/leave-types/`

List, or create (ADMIN only), a kind of absence. Names are workspace data, not a choice
enum — compiling "annual leave" into the product would make every workspace inherit one
organisation's vocabulary.

`consumes_capacity: false` marks an absence that does not remove the person from work
(working remotely, for instance). It still draws on the wallchart; it does not subtract
from capacity. `requires_approval: false` makes a logged absence land approved.

## `GET | POST …/availability/leaves/` · `PATCH …/availability/leaves/<id>/`

| Query            | Required | Notes                                           |
| ---------------- | -------- | ----------------------------------------------- |
| `from` / `to`    | yes      | `YYYY-MM-DD`                                    |
| `member_ids`     | no       | Comma-separated                                 |
| `include_closed` | no       | `true` also returns cancelled and rejected rows |

```json
{
  "leave_type": "…",
  "start_date": "2026-08-03",
  "end_date": "2026-08-05",
  "start_day_part": "afternoon",
  "end_day_part": "full",
  "reason": "optional",
  "member": "…"
}
```

`member` is admins-only and defaults to the caller — a declaration somebody else made on
your behalf is not a declaration.

**Half days.** On a single-day request both parts must match (`morning`/`morning` or
`afternoon`/`afternoon`). On a range, the only partial ends are "starts after lunch"
(`start_day_part: afternoon`) and "ends at lunch" (`end_day_part: morning`). A multi-day
leave starting in the _morning_ is rejected: that is a full first day, and allowing two
spellings of one thing makes the day count depend on which was used.

`PATCH` currently accepts `{"action": "cancel"}` only; approving and rejecting arrive with
the decision workflow. Cancelling does not delete — the row stays so history is honest, and
it simply stops counting against availability.

**Reasons are redacted by omission.** A reader not entitled to `reason` or `decision_note`
gets a payload without those keys, not keys set to null. A present key with a null value
still tells a colleague there was a reason.

## `GET | POST …/availability/events/`

Team events: training, an offsite, a release day. `audience` is declared
(`all_members` / `selected_members`) rather than inferred from whether attendees happen to
be listed — the same reasoning as ADR 0007's "a folder is declared, not inferred".
`consumes_capacity` is `false` by default, because a release date is something nobody
attends.

Creating requires ADMIN.

## How absence reaches the rest of the surface

Occupancy is computed as **two booleans per date** — morning taken, afternoon taken —
combined by union. That is why a half day of leave on the same Wednesday as an all-hands
removes exactly one day: summing fractions would remove one and a half, and a union cannot
exceed the day it describes.

Only **approved** absences bind. A pending request has not been decided, and planning
against a guess is worse than planning against nothing.

`GET …/availability/schedule/` and the overlap endpoint both subtract occupancy, so a
person cannot be away on the wallchart and reachable in the slot finder.

## Agent parity

Every action above has an equivalent MCP tool and CLI command, per guideline A3.

| Action             | MCP                     | CLI                                 |
| ------------------ | ----------------------- | ----------------------------------- |
| Read the week      | `availability_schedule` | `plane-qa availability schedule`    |
| Find a shared slot | `availability_overlap`  | `plane-qa availability overlap`     |
| List calendars     | `work_calendar_list`    | `plane-qa availability calendars`   |
| Read profiles      | `availability_schedule` | `plane-qa availability profiles`    |
| Set working hours  | `work_profile_set`      | `plane-qa availability set-profile` |
