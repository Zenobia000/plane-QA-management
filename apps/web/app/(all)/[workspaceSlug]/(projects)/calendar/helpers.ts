/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TAvailabilityCapabilities, TAvailabilityTab, TAvailabilityWindow } from "@plane/types";

export const AVAILABILITY_TABS: TAvailabilityTab[] = ["schedule", "leave", "allocation", "settings"];

type TAvailabilityPath = {
  workspaceSlug: string;
  tab?: TAvailabilityTab;
};

export const availabilityPath = ({ workspaceSlug, tab }: TAvailabilityPath) =>
  tab ? `/${workspaceSlug}/calendar/${tab}` : `/${workspaceSlug}/calendar`;

/**
 * Which capability flag decides whether a tab has anything to render.
 *
 * The schedule tab needs `schedule`; the common-slot finder inside it is gated separately
 * by `overlap` so the week view can ship before the finder does.
 */
const TAB_CAPABILITY: Record<TAvailabilityTab, keyof TAvailabilityCapabilities["capabilities"] | null> = {
  schedule: "schedule",
  leave: "leave",
  allocation: "allocation",
  // Settings is where the data gets created, so it can never be gated on that data
  // existing — a workspace with nothing configured would be unable to configure anything.
  settings: null,
};

export const isTabReady = (capability: TAvailabilityCapabilities | null, tab: TAvailabilityTab): boolean => {
  const flag = TAB_CAPABILITY[tab];
  if (flag === null) return true;
  return Boolean(capability?.enabled && capability.capabilities[flag]);
};

// ---------------------------------------------------------------------------
// Time zones
//
// Done with `Intl` rather than a library. The one operation this view needs -- "what UTC
// instant is local midnight on this date in that zone" -- is two lines of platform API, and
// `date-fns-tz` is not in the workspace. Adding a dependency to avoid twelve lines that are
// covered by tests is the worse trade.
// ---------------------------------------------------------------------------

/** How far ahead of UTC `timeZone` is at `at`, in minutes. Negative west of Greenwich. */
export const zoneOffsetMinutes = (at: Date, timeZone: string): number => {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(at);
  const lookup = Object.fromEntries(parts.map((part) => [part.type, part.value])) as Record<string, string>;
  const asIfUTC = Date.UTC(
    Number(lookup.year),
    Number(lookup.month) - 1,
    Number(lookup.day),
    // `hour12: false` renders midnight as 24 in some engines.
    Number(lookup.hour) % 24,
    Number(lookup.minute),
    Number(lookup.second)
  );
  return (asIfUTC - at.getTime()) / 60_000;
};

/**
 * The instant at which `isoDate` begins in `timeZone`.
 *
 * Two passes: the offset is itself a function of the instant, so the first guess can land
 * on the wrong side of a daylight-saving change and needs re-reading once corrected.
 */
export const startOfDayInZone = (isoDate: string, timeZone: string): Date => {
  const naive = new Date(`${isoDate}T00:00:00Z`);
  const first = new Date(naive.getTime() - zoneOffsetMinutes(naive, timeZone) * 60_000);
  return new Date(naive.getTime() - zoneOffsetMinutes(first, timeZone) * 60_000);
};

const DAY_MS = 24 * 60 * 60 * 1000;

export type TBarPosition = { leftPercent: number; widthPercent: number };

/**
 * Where a window sits on a 24-hour axis that starts at `dayStart`.
 *
 * Clamped, so a window running past midnight draws up to the edge instead of overflowing
 * its row -- a person in Auckland working "Tuesday" straddles two UTC days, and the axis is
 * the viewer's day, not theirs.
 */
export const barPosition = (window: TAvailabilityWindow, dayStart: Date): TBarPosition | null => {
  const start = new Date(window.start).getTime();
  const end = new Date(window.end).getTime();
  const from = dayStart.getTime();
  const to = from + DAY_MS;

  const visibleStart = Math.max(start, from);
  const visibleEnd = Math.min(end, to);
  if (visibleEnd <= visibleStart) return null;

  return {
    leftPercent: ((visibleStart - from) / DAY_MS) * 100,
    widthPercent: ((visibleEnd - visibleStart) / DAY_MS) * 100,
  };
};

/** `HH:mm` for an instant, read in the viewer's chosen zone. */
export const clockInZone = (iso: string, timeZone: string): string =>
  new Intl.DateTimeFormat("en-GB", {
    timeZone,
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));

/** ISO date (`YYYY-MM-DD`) of an instant, read in the viewer's chosen zone. */
export const dateInZone = (iso: string | Date, timeZone: string): string => {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(typeof iso === "string" ? new Date(iso) : iso);
  return parts;
};

/** Monday-to-Sunday around `anchor`, as ISO dates. */
export const weekOf = (anchor: Date, timeZone: string): string[] => {
  const anchorDate = dateInZone(anchor, timeZone);
  const midnight = startOfDayInZone(anchorDate, timeZone);
  // getUTCDay() on the local midnight instant would read the UTC weekday, which can differ.
  const isoWeekday = Number(
    new Intl.DateTimeFormat("en-US", { timeZone, weekday: "short" })
      .format(midnight)
      .replace(/Mon|Tue|Wed|Thu|Fri|Sat|Sun/, (day) =>
        String(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].indexOf(day) + 1)
      )
  );

  const days: string[] = [];
  for (let offset = 0; offset < 7; offset += 1) {
    const shift = offset - (isoWeekday - 1);
    days.push(dateInZone(new Date(midnight.getTime() + shift * DAY_MS), timeZone));
  }
  return days;
};

export const addDays = (isoDate: string, days: number): string => {
  const shifted = new Date(`${isoDate}T00:00:00Z`);
  shifted.setUTCDate(shifted.getUTCDate() + days);
  return shifted.toISOString().slice(0, 10);
};

/** Every ISO date in a `YYYY-MM` month. */
export const monthGrid = (month: string): string[] => {
  const [year, index] = month.split("-").map(Number);
  const days = new Date(Date.UTC(year, index, 0)).getUTCDate();
  return Array.from({ length: days }, (_, offset) => `${month}-${String(offset + 1).padStart(2, "0")}`);
};

export const shiftMonth = (month: string, by: number): string => {
  const [year, index] = month.split("-").map(Number);
  const shifted = new Date(Date.UTC(year, index - 1 + by, 1));
  return `${shifted.getUTCFullYear()}-${String(shifted.getUTCMonth() + 1).padStart(2, "0")}`;
};

/** Whether `day` falls inside an inclusive ISO date span. String compare is safe for ISO. */
export const spanCovers = (start: string, end: string, day: string): boolean => day >= start && day <= end;
