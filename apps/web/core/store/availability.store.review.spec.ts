import { describe, expect, it, vi } from "vitest";
import type { AvailabilityService } from "@plane/services";
import { AvailabilityStore } from "./availability.store";

const capability = {
  enabled: true,
  stage: "t",
  capabilities: { schedule: true, overlap: true, leave: true, allocation: true, capacity: true },
};

const serviceMock = (overrides: Partial<AvailabilityService> = {}) =>
  ({
    getCapabilities: vi.fn().mockResolvedValue(capability),
    getSchedule: vi.fn().mockResolvedValue({ from: "", to: "", members: [] }),
    getLeaveTypes: vi.fn().mockResolvedValue([]),
    getLeaves: vi.fn().mockResolvedValue([]),
    getTeamEvents: vi.fn().mockResolvedValue([]),
    updateProfile: vi.fn().mockResolvedValue({ id: "p", member: "m" }),
    ...overrides,
  }) as unknown as AvailabilityService;

describe("AvailabilityStore — workspace scoping", () => {
  it("drops the previous workspace's rows when the slug changes", async () => {
    const store = new AvailabilityStore(serviceMock());
    await store.fetchMonth("acme", "2026-08-01", "2026-08-31");
    // Simulate rows from workspace A having landed.
    store.leaves = [{ id: "l1", member: "ana" }] as never;

    await store.fetchMonth("other", "2026-08-01", "2026-08-31");

    // A's absences must not sit under B's member list even for a moment.
    expect(store.leaves).toEqual([]);
  });

  it("clears the previous workspace even when the new fetch fails", async () => {
    const store = new AvailabilityStore(
      serviceMock({ getLeaves: vi.fn().mockRejectedValue(new Error("nope")) } as never)
    );
    store.leaves = [{ id: "l1", member: "ana" }] as never;

    await store.fetchMonth("other", "2026-08-01", "2026-08-31");

    expect(store.leaves).toEqual([]);
    expect(store.error).toBeTruthy();
  });

  it("does not re-scope when the slug is unchanged", async () => {
    // Asserted on `capability` rather than `leaves`: `fetchMonth` legitimately overwrites
    // the collections it fetches, so only state it does *not* touch shows whether the
    // scope reset fired.
    const service = serviceMock();
    const store = new AvailabilityStore(service);
    await store.fetchCapabilities("acme");

    await store.fetchMonth("acme", "2026-08-01", "2026-08-31");

    expect(store.capability).toEqual(capability);
    expect(store.hydratedFor).toBe("acme");
    expect(service.getCapabilities).toHaveBeenCalledTimes(1);
  });

  it("re-fetches the capability payload after a workspace change", async () => {
    const service = serviceMock();
    const store = new AvailabilityStore(service);
    await store.fetchCapabilities("acme");

    await store.fetchMonth("other", "2026-08-01", "2026-08-31");
    await store.fetchCapabilities("other");

    // `hydratedFor` was cleared by the scope reset, so the guard cannot serve A's payload
    // for B.
    expect(service.getCapabilities).toHaveBeenCalledTimes(2);
  });
});

describe("AvailabilityStore — updateProfile reports refusals", () => {
  it("returns false and records the message when the server refuses", async () => {
    const store = new AvailabilityStore(
      serviceMock({
        updateProfile: vi.fn().mockRejectedValue({ error: ["Core hours must fall inside the working window."] }),
      } as never)
    );

    const saved = await store.updateProfile("acme", "m", { core_hours_start: "07:00" });

    // Previously this rethrew, so the form's error banner stayed empty and the member
    // believed a refused write had been saved.
    expect(saved).toBe(false);
    expect(store.error).toBe("Core hours must fall inside the working window.");
  });

  it("returns true on success", async () => {
    const store = new AvailabilityStore(serviceMock());

    expect(await store.updateProfile("acme", "m", { hours_per_day: "6" })).toBe(true);
    expect(store.error).toBeNull();
  });
});
