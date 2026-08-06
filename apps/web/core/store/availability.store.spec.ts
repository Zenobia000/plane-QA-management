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
});
