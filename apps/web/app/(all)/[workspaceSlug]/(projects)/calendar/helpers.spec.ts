import { describe, expect, it } from "vitest";
import type { TAvailabilityCapabilities, TAvailabilityWindow } from "@plane/types";
import {
  addDays,
  availabilityPath,
  barPosition,
  clockInZone,
  dateInZone,
  isTabReady,
  monthGrid,
  shiftMonth,
  spanCovers,
  startOfDayInZone,
  weekOf,
  zoneOffsetMinutes,
} from "./helpers";

const capability = (overrides: Partial<TAvailabilityCapabilities["capabilities"]> = {}): TAvailabilityCapabilities => ({
  enabled: true,
  stage: "test",
  capabilities: { schedule: false, overlap: false, leave: false, allocation: false, capacity: false, ...overrides },
});

const window = (start: string, end: string): TAvailabilityWindow => ({
  start,
  end,
  minutes: (new Date(end).getTime() - new Date(start).getTime()) / 60_000,
});

describe("availabilityPath", () => {
  it("addresses each tab separately so a view is linkable", () => {
    expect(availabilityPath({ workspaceSlug: "acme", tab: "schedule" })).toBe("/acme/calendar/schedule");
    expect(availabilityPath({ workspaceSlug: "acme", tab: "allocation" })).toBe("/acme/calendar/allocation");
  });

  it("falls back to the bare path, which redirects to schedule", () => {
    expect(availabilityPath({ workspaceSlug: "acme" })).toBe("/acme/calendar");
  });
});

describe("isTabReady", () => {
  it("is false before the capability payload arrives", () => {
    expect(isTabReady(null, "schedule")).toBe(false);
  });

  it("gates each tab on its own flag", () => {
    const partial = capability({ leave: true });

    expect(isTabReady(partial, "leave")).toBe(true);
    expect(isTabReady(partial, "schedule")).toBe(false);
    expect(isTabReady(partial, "allocation")).toBe(false);
  });

  it("gates the whole surface when the module is switched off", () => {
    const disabled = { ...capability({ leave: true }), enabled: false };

    expect(isTabReady(disabled, "leave")).toBe(false);
  });

  it("does not let the overlap flag stand in for the schedule view", () => {
    // The week view and the common-slot finder inside it ship in that order, so a build
    // where only `overlap` were true must still render the schedule empty state.
    expect(isTabReady(capability({ overlap: true }), "schedule")).toBe(false);
  });
});

describe("zoneOffsetMinutes", () => {
  it("reads a fixed-offset zone", () => {
    expect(zoneOffsetMinutes(new Date("2026-08-03T00:00:00Z"), "Asia/Taipei")).toBe(480);
  });

  it("follows a zone across its daylight-saving change", () => {
    expect(zoneOffsetMinutes(new Date("2026-08-03T00:00:00Z"), "Europe/Berlin")).toBe(120);
    expect(zoneOffsetMinutes(new Date("2026-01-05T00:00:00Z"), "Europe/Berlin")).toBe(60);
  });

  it("reads a zone west of Greenwich as negative", () => {
    expect(zoneOffsetMinutes(new Date("2026-08-03T00:00:00Z"), "America/Los_Angeles")).toBe(-420);
  });
});

describe("startOfDayInZone", () => {
  it("finds the instant a day begins in a fixed-offset zone", () => {
    expect(startOfDayInZone("2026-08-03", "Asia/Taipei").toISOString()).toBe("2026-08-02T16:00:00.000Z");
  });

  it("finds it either side of a daylight-saving change", () => {
    expect(startOfDayInZone("2026-08-03", "Europe/Berlin").toISOString()).toBe("2026-08-02T22:00:00.000Z");
    expect(startOfDayInZone("2026-01-05", "Europe/Berlin").toISOString()).toBe("2026-01-04T23:00:00.000Z");
  });

  it("is exact on the day the clocks go forward", () => {
    // Europe/Berlin springs forward at 02:00 local on 2026-03-29.
    expect(startOfDayInZone("2026-03-29", "Europe/Berlin").toISOString()).toBe("2026-03-28T23:00:00.000Z");
    expect(startOfDayInZone("2026-03-30", "Europe/Berlin").toISOString()).toBe("2026-03-29T22:00:00.000Z");
  });

  it("agrees with UTC for UTC", () => {
    expect(startOfDayInZone("2026-08-03", "UTC").toISOString()).toBe("2026-08-03T00:00:00.000Z");
  });
});

describe("barPosition", () => {
  const dayStart = new Date("2026-08-03T00:00:00Z");

  it("places a window by its share of the axis", () => {
    const position = barPosition(window("2026-08-03T06:00:00Z", "2026-08-03T12:00:00Z"), dayStart);

    expect(position).toEqual({ leftPercent: 25, widthPercent: 25 });
  });

  it("clamps a window that starts before the axis", () => {
    const position = barPosition(window("2026-08-02T20:00:00Z", "2026-08-03T06:00:00Z"), dayStart);

    expect(position).toEqual({ leftPercent: 0, widthPercent: 25 });
  });

  it("clamps a window that runs past midnight rather than overflowing the row", () => {
    // Somebody in Auckland working "Tuesday" straddles two UTC days; the axis is the
    // viewer's day, not theirs.
    const position = barPosition(window("2026-08-03T18:00:00Z", "2026-08-04T03:00:00Z"), dayStart);

    expect(position).toEqual({ leftPercent: 75, widthPercent: 25 });
  });

  it("drops a window that does not touch the axis at all", () => {
    expect(barPosition(window("2026-08-05T09:00:00Z", "2026-08-05T17:00:00Z"), dayStart)).toBeNull();
  });

  it("drops a window that merely ends where the axis begins", () => {
    expect(barPosition(window("2026-08-02T20:00:00Z", "2026-08-03T00:00:00Z"), dayStart)).toBeNull();
  });
});

describe("clockInZone", () => {
  it("renders one instant differently for two viewers", () => {
    expect(clockInZone("2026-08-03T07:00:00Z", "Asia/Taipei")).toBe("15:00");
    expect(clockInZone("2026-08-03T07:00:00Z", "Europe/Berlin")).toBe("09:00");
  });
});

describe("dateInZone", () => {
  it("can land on a different calendar day than UTC", () => {
    expect(dateInZone("2026-08-03T20:00:00Z", "Asia/Taipei")).toBe("2026-08-04");
    expect(dateInZone("2026-08-03T20:00:00Z", "UTC")).toBe("2026-08-03");
  });
});

describe("weekOf", () => {
  it("runs Monday to Sunday around the anchor", () => {
    const days = weekOf(new Date("2026-08-05T12:00:00Z"), "UTC");

    expect(days).toHaveLength(7);
    expect(days[0]).toBe("2026-08-03");
    expect(days[6]).toBe("2026-08-09");
  });

  it("uses the viewer's zone to decide which week they are in", () => {
    // 23:00 UTC Sunday is already Monday in Taipei, so the weeks differ.
    expect(weekOf(new Date("2026-08-09T23:00:00Z"), "UTC")[0]).toBe("2026-08-03");
    expect(weekOf(new Date("2026-08-09T23:00:00Z"), "Asia/Taipei")[0]).toBe("2026-08-10");
  });

  it("treats Monday as the first day, not Sunday", () => {
    expect(weekOf(new Date("2026-08-03T12:00:00Z"), "UTC")[0]).toBe("2026-08-03");
  });
});

describe("addDays", () => {
  it("crosses a month boundary", () => {
    expect(addDays("2026-08-31", 1)).toBe("2026-09-01");
  });

  it("crosses a year boundary backwards", () => {
    expect(addDays("2027-01-01", -1)).toBe("2026-12-31");
  });

  it("steps a whole week", () => {
    expect(addDays("2026-08-03", 7)).toBe("2026-08-10");
  });
});

describe("monthGrid", () => {
  it("covers a 31-day month", () => {
    const days = monthGrid("2026-08");
    expect(days).toHaveLength(31);
    expect(days[0]).toBe("2026-08-01");
    expect(days[30]).toBe("2026-08-31");
  });

  it("covers a 30-day month", () => {
    expect(monthGrid("2026-09")).toHaveLength(30);
  });

  it("gets February right in a common year", () => {
    expect(monthGrid("2026-02")).toHaveLength(28);
  });

  it("gets February right in a leap year", () => {
    expect(monthGrid("2028-02")).toHaveLength(29);
  });
});

describe("shiftMonth", () => {
  it("steps forward across a year boundary", () => {
    expect(shiftMonth("2026-12", 1)).toBe("2027-01");
  });

  it("steps back across a year boundary", () => {
    expect(shiftMonth("2026-01", -1)).toBe("2025-12");
  });

  it("keeps the zero-padded form", () => {
    expect(shiftMonth("2026-08", 1)).toBe("2026-09");
  });
});

describe("spanCovers", () => {
  it("includes both ends", () => {
    expect(spanCovers("2026-08-03", "2026-08-05", "2026-08-03")).toBe(true);
    expect(spanCovers("2026-08-03", "2026-08-05", "2026-08-05")).toBe(true);
  });

  it("excludes days outside", () => {
    expect(spanCovers("2026-08-03", "2026-08-05", "2026-08-02")).toBe(false);
    expect(spanCovers("2026-08-03", "2026-08-05", "2026-08-06")).toBe(false);
  });

  it("compares correctly across a month boundary", () => {
    // String comparison is only safe because the format is zero-padded ISO.
    expect(spanCovers("2026-08-30", "2026-09-02", "2026-09-01")).toBe(true);
    expect(spanCovers("2026-08-30", "2026-09-02", "2026-08-29")).toBe(false);
  });
});
