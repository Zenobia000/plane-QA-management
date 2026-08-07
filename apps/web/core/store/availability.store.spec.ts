import { describe, expect, it, vi } from "vitest";
import type { AvailabilityService } from "@plane/services";
import type { TAvailabilityCapabilities } from "@plane/types";
import { AvailabilityStore } from "./availability.store";

const capability: TAvailabilityCapabilities = {
  enabled: true,
  stage: "architecture-slice",
  capabilities: { schedule: false, overlap: false, leave: false, allocation: false, capacity: false },
};

const serviceMock = (impl?: Partial<AvailabilityService>) =>
  ({
    getCapabilities: vi.fn().mockResolvedValue(capability),
    ...impl,
  }) as unknown as AvailabilityService;

describe("AvailabilityStore", () => {
  it("deduplicates concurrent loads", async () => {
    const service = serviceMock();
    const store = new AvailabilityStore(service);

    await Promise.all([store.fetchCapabilities("acme"), store.fetchCapabilities("acme")]);

    expect(service.getCapabilities).toHaveBeenCalledTimes(1);
  });

  it("does not refetch when switching between tabs of the same workspace", async () => {
    const service = serviceMock();
    const store = new AvailabilityStore(service);

    await store.fetchCapabilities("acme");
    await store.fetchCapabilities("acme");

    expect(service.getCapabilities).toHaveBeenCalledTimes(1);
    expect(store.capability).toEqual(capability);
  });

  it("refetches when the workspace changes", async () => {
    const service = serviceMock();
    const store = new AvailabilityStore(service);

    await store.fetchCapabilities("acme");
    await store.fetchCapabilities("other");

    expect(service.getCapabilities).toHaveBeenCalledTimes(2);
  });

  it("surfaces a failure and stays unhydrated so a retry is possible", async () => {
    const service = serviceMock({
      getCapabilities: vi.fn().mockRejectedValue(new Error("forbidden")),
    });
    const store = new AvailabilityStore(service);

    await store.fetchCapabilities("acme");

    expect(store.error).toBe("forbidden");
    expect(store.capability).toBeNull();
    expect(store.hydratedFor).toBeNull();
    expect(store.loading).toBe(false);

    // A guest who was told no must not be stuck with a permanently empty page if their
    // role changes; leaving hydratedFor null is what lets the next mount ask again.
    await store.fetchCapabilities("acme");
    expect(service.getCapabilities).toHaveBeenCalledTimes(2);
  });

  it("tells the caller a refused write was refused", async () => {
    // Without this the form has no way to distinguish the two, and the only safe guess —
    // close and clear — deletes what somebody just typed the moment it was rejected.
    const service = serviceMock({
      createLeave: vi.fn().mockRejectedValue({ error: "Leave overlaps an existing request" }),
    });
    const store = new AvailabilityStore(service);

    const recorded = await store.createLeave("acme", {
      leave_type: "type-annual",
      start_date: "2026-08-12",
      end_date: "2026-08-12",
    });

    expect(recorded).toBe(false);
    expect(store.error).toBe("Leave overlaps an existing request");
    expect(store.leaves).toEqual([]);
  });

  it("clears a previous complaint once a write goes through", async () => {
    const leave = { id: "leave-1", member: "ana" };
    const service = serviceMock({
      createLeave: vi.fn().mockRejectedValueOnce(new Error("nope")).mockResolvedValueOnce(leave),
    });
    const store = new AvailabilityStore(service);
    const payload = { leave_type: "type-annual", start_date: "2026-08-12", end_date: "2026-08-12" };

    await store.createLeave("acme", payload);
    expect(store.error).toBe("nope");

    // A stale error next to a successful save reads as a second failure.
    expect(await store.createLeave("acme", payload)).toBe(true);
    expect(store.error).toBeNull();
    expect(store.leaves).toHaveLength(1);
  });
});
