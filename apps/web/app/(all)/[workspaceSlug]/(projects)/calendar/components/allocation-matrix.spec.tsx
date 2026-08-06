// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { TAllocationMatrix } from "@plane/types";

const { useAvailabilityMock, useMemberMock, useProjectMock, usePermissionsMock } = vi.hoisted(() => ({
  useAvailabilityMock: vi.fn(),
  useMemberMock: vi.fn(),
  useProjectMock: vi.fn(),
  usePermissionsMock: vi.fn(),
}));

vi.mock("@/hooks/store/use-availability", () => ({ useAvailability: useAvailabilityMock }));
vi.mock("@/hooks/store/use-member", () => ({ useMember: useMemberMock }));
vi.mock("@/hooks/store/use-project", () => ({ useProject: useProjectMock }));
vi.mock("@/hooks/store/user", () => ({ useUserPermissions: usePermissionsMock }));

import { AllocationMatrix } from "./allocation-matrix";

/** Ana is split across both projects; Bob is on neither. */
const matrix: TAllocationMatrix = {
  allocations: [
    { member_id: "ana", project_id: "alpha", allocation_percent: 50 },
    { member_id: "ana", project_id: "beta", allocation_percent: 50 },
  ],
  totals: { ana: 100, bob: 0 },
};

const mount = (over: { allocations?: TAllocationMatrix | null; error?: string | null; admin?: boolean } = {}) => {
  const setAllocation = vi.fn().mockResolvedValue(true);

  useAvailabilityMock.mockReturnValue({
    allocations: over.allocations === undefined ? matrix : over.allocations,
    fetchAllocations: vi.fn(),
    setAllocation,
    error: over.error ?? null,
  });
  useMemberMock.mockReturnValue({
    getUserDetails: (id: string) => ({ display_name: id === "ana" ? "Ana" : "Bob", email: `${id}@plane.so` }),
    workspace: { fetchWorkspaceMembers: vi.fn(), workspaceMemberIds: ["ana", "bob"] },
  });
  useProjectMock.mockReturnValue({
    workspaceProjectIds: ["alpha", "beta"],
    getProjectById: (id: string) => ({ name: id === "alpha" ? "Alpha" : "Beta" }),
  });
  usePermissionsMock.mockReturnValue({ allowPermissions: () => over.admin ?? true });

  render(
    <MemoryRouter initialEntries={["/acme/calendar/allocation"]}>
      <Routes>
        <Route path=":workspaceSlug/calendar/allocation" element={<AllocationMatrix />} />
      </Routes>
    </MemoryRouter>
  );

  return { setAllocation };
};

afterEach(cleanup);

describe("AllocationMatrix", () => {
  it("keeps a row for somebody allocated to nothing", () => {
    mount();

    // Spare capacity is exactly what a person planning new work is looking for. A matrix
    // that hides the unallocated answers the opposite question.
    expect(screen.getByText("Bob")).toBeDefined();
    expect(screen.getByText("team_calendar.allocation.unallocated")).toBeDefined();
  });

  it("puts each member's percentages in the project's own column", () => {
    mount();

    expect(screen.getByText("Alpha")).toBeDefined();
    const filled = screen.getAllByRole("spinbutton").map((input) => (input as HTMLInputElement).value);
    expect(filled).toEqual(["50", "50", "0", "0"]);
  });

  it("totals the row so the split is readable while it is being decided", () => {
    mount();

    expect(screen.getByText("100%")).toBeDefined();
    expect(screen.getByText("0%")).toBeDefined();
  });

  it("writes only the cell that actually changed", async () => {
    const user = userEvent.setup();
    const { setAllocation } = mount();

    const [alpha] = screen.getAllByRole("spinbutton");
    await user.click(alpha);
    await user.tab();

    expect(setAllocation).not.toHaveBeenCalled();

    await user.clear(alpha);
    await user.type(alpha, "70");
    await user.tab();

    expect(setAllocation).toHaveBeenCalledWith("acme", "ana", "alpha", 70);
  });

  it("lets a non-admin read the split without editing it", () => {
    mount({ admin: false });

    // Readable by everyone on purpose: a member should be able to see why their week is
    // carved up the way it is, even though only an admin can carve it.
    expect(screen.getByText(/team_calendar.allocation.admin_only/)).toBeDefined();
    for (const input of screen.getAllByRole("spinbutton")) expect((input as HTMLInputElement).disabled).toBe(true);
  });

  it("does not tell an admin the page is read-only", () => {
    mount({ admin: true });

    expect(screen.queryByText(/team_calendar.allocation.admin_only/)).toBeNull();
    for (const input of screen.getAllByRole("spinbutton")) expect((input as HTMLInputElement).disabled).toBe(false);
  });

  it("says what the server refused rather than leaving a stale number on screen", () => {
    mount({ error: "Ana would be allocated 150% across projects" });

    expect(screen.getByText("Ana would be allocated 150% across projects")).toBeDefined();
  });

  it("draws the grid before the matrix has arrived", () => {
    mount({ allocations: null });

    // Members and projects come from their own stores, so the table is not blocked on
    // the allocation fetch; every cell simply reads zero until it lands.
    expect(screen.getByText("Ana")).toBeDefined();
    expect(screen.getAllByRole("spinbutton")).toHaveLength(4);
  });
});
