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
export type TAvailabilityTab = "schedule" | "leave" | "allocation";
