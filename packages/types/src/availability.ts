/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * What the team-calendar surface can currently do.
 *
 * Every flag starts false and is flipped by the slice that implements it, so the client
 * can ship its navigation, route and tabs before any of them exist and render an honest
 * empty state for the rest. See `docs/planning/team-calendar-wbs.md`.
 */
export type TAvailabilityCapabilities = {
  enabled: boolean;
  stage: string;
  capabilities: {
    schedule: boolean;
    overlap: boolean;
    leave: boolean;
    allocation: boolean;
    capacity: boolean;
  };
};

/**
 * The three tabs, which are three different questions -- see `docs/planning/team-calendar.md`.
 *
 * `schedule` answers "when can we talk", `leave` answers "who is out", `allocation` answers
 * "how is one person's time split across projects". They are deliberately not one screen:
 * absence belongs to a person, allocation belongs to the person-project pair.
 */
export type TAvailabilityTab = "schedule" | "leave" | "allocation" | "settings";

/**
 * One reachable stretch, as absolute UTC instants.
 *
 * Never a local wall-clock time: "Tuesday 09:00" is not comparable across two cities, and
 * the whole point of this surface is comparing across cities. The viewer's zone is applied
 * at render, once.
 */
export type TAvailabilityWindow = {
  start: string;
  end: string;
  minutes: number;
};

export type TMemberSchedule = {
  member_id: string;
  timezone: string;
  calendar_id: string | null;
  hours_per_day: number;
  working: TAvailabilityWindow[];
  /** Narrower than `working`, and only where the member committed to one. */
  core: TAvailabilityWindow[];
};

export type TAvailabilitySchedule = {
  from: string;
  to: string;
  members: TMemberSchedule[];
};

export type TOverlapRequest = {
  member_ids: string[];
  date_from: string;
  date_to: string;
  duration_minutes?: number;
};

export type TOverlapResult = {
  duration_minutes: number;
  core: TAvailabilityWindow[];
  working: TAvailabilityWindow[];
  /** Requested but not members of this workspace. */
  unknown_members: string[];
  /** Members who have declared no hours, so they cannot be part of any answer. */
  members_without_hours: string[];
};

export type TWorkCalendar = {
  id: string;
  name: string;
  timezone: string;
  /** ISO weekday numbers, Monday = 1. */
  working_weekdays: number[];
  is_default: boolean;
};

export type TMemberWorkProfile = {
  id: string;
  member: string;
  work_calendar: string | null;
  timezone: string | null;
  work_start_time: string;
  work_end_time: string;
  core_hours_start: string | null;
  core_hours_end: string | null;
  hours_per_day: string;
  approver: string | null;
};

/** A member who has declared nothing reads as this rather than as a 404. */
export type TUndeclaredWorkProfile = {
  member: string;
  declared: false;
};

export type TMemberWorkProfileInput = Partial<{
  work_calendar: string | null;
  timezone: string | null;
  work_start_time: string;
  work_end_time: string;
  core_hours_start: string | null;
  core_hours_end: string | null;
  hours_per_day: string;
  approver: string | null;
  /** `null` means "leave unchanged" for every other field, so withdrawing needs its own flag. */
  clear_core_hours: boolean;
}>;

/** Which half of a day an absence covers. Granularity stops here — see ADR 0008. */
export type TDayPart = "full" | "morning" | "afternoon";

export type TLeaveStatus = "pending" | "approved" | "rejected" | "cancelled";

export type TLeaveType = {
  id: string;
  name: string;
  colour: string;
  /** False for absences that do not remove the person from work, e.g. working remotely. */
  consumes_capacity: boolean;
  requires_approval: boolean;
  is_active: boolean;
  sort_order: number;
};

/**
 * `reason` and `decision_note` are **absent**, not null, for readers not entitled to them.
 * A present key with a null value still tells a colleague there was a reason.
 */
export type TMemberLeave = {
  id: string;
  member: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  start_day_part: TDayPart;
  end_day_part: TDayPart;
  status: TLeaveStatus;
  reason?: string;
  decision_note?: string;
  decided_by: string | null;
  decided_at: string | null;
};

export type TMemberLeaveInput = {
  leave_type: string;
  start_date: string;
  end_date: string;
  start_day_part?: TDayPart;
  end_day_part?: TDayPart;
  reason?: string;
  /** Admins only; defaults to the caller. */
  member?: string;
};

export type TTeamEvent = {
  id: string;
  project: string | null;
  title: string;
  description: string;
  start_date: string;
  end_date: string;
  start_day_part: TDayPart;
  end_day_part: TDayPart;
  colour: string;
  consumes_capacity: boolean;
  /** Declared, not inferred from whether attendees happen to be listed. */
  audience: "all_members" | "selected_members";
  attendee_ids: string[];
};

export type TAllocationMatrix = {
  allocations: { member_id: string; project_id: string; allocation_percent: number }[];
  /** Per-member sum. Over 100 is impossible — the server refuses the write. */
  totals: Record<string, number>;
};

export type TCycleCapacityMember = {
  member_id: string;
  allocation_percent: number;
  working_days: number;
  hours_per_day: number;
  gross_hours: number;
  absence_hours: number;
  available_hours: number;
  /** False when this member has never declared working hours, so their capacity reads zero. */
  declared: boolean;
};

export type TCycleCapacity = {
  ready: boolean;
  reason?: string;
  start_date?: string;
  end_date?: string;
  members: TCycleCapacityMember[];
  available_hours?: number;
  /** True when nobody has been allocated, so everyone is counted at 100%. */
  allocation_is_assumed?: boolean;
  undeclared_members?: string[];
  /** False unless the project estimates in time — points and hours are not commensurate. */
  committed_comparable?: boolean;
  committed_hours?: number | null;
  estimate_type?: string | null;
};

export type TCalendarDayKind = "holiday" | "makeup_workday";

/**
 * A date that overrides its calendar's weekday rule.
 *
 * `makeup_workday` is the one a weekday-mask model cannot express: a Saturday the whole
 * country works to bridge a long weekend.
 */
export type TCalendarDay = {
  id: string;
  date: string;
  name: string;
  kind: TCalendarDayKind;
};

export type TCalendarDayInput = {
  date: string;
  name: string;
  kind: TCalendarDayKind;
};

export type TWorkCalendarInput = Partial<{
  name: string;
  timezone: string;
  working_weekdays: number[];
  is_default: boolean;
}>;

export type TLeaveTypeInput = Partial<{
  name: string;
  colour: string;
  consumes_capacity: boolean;
  requires_approval: boolean;
  is_active: boolean;
  sort_order: number;
}>;
