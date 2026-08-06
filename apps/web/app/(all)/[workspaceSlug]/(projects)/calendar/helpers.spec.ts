import { describe, expect, it } from "vitest";
import type { TAvailabilityCapabilities } from "@plane/types";
import { availabilityPath, isTabReady } from "./helpers";

const capability = (overrides: Partial<TAvailabilityCapabilities["capabilities"]> = {}): TAvailabilityCapabilities => ({
  enabled: true,
  stage: "test",
  capabilities: { schedule: false, overlap: false, leave: false, allocation: false, capacity: false, ...overrides },
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
