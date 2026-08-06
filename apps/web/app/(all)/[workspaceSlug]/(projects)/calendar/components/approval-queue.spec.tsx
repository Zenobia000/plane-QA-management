// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { TLeaveType, TMemberLeave } from "@plane/types";

const { useAvailabilityMock, useMemberMock } = vi.hoisted(() => ({
  useAvailabilityMock: vi.fn(),
  useMemberMock: vi.fn(),
}));

vi.mock("@/hooks/store/use-availability", () => ({ useAvailability: useAvailabilityMock }));
vi.mock("@/hooks/store/use-member", () => ({ useMember: useMemberMock }));

import { ApprovalQueue } from "./approval-queue";

const annual: TLeaveType = {
  id: "type-annual",
  name: "Annual",
  colour: "#2E7D32",
  consumes_capacity: true,
  requires_approval: true,
  is_active: true,
  sort_order: 1,
};

const request = (over: Partial<TMemberLeave> = {}): TMemberLeave => ({
  id: "leave-1",
  member: "ana",
  leave_type: annual.id,
  start_date: "2026-08-12",
  end_date: "2026-08-12",
  start_day_part: "full",
  end_day_part: "full",
  status: "pending",
  decided_by: null,
  decided_at: null,
  ...over,
});

const mount = (pendingLeaves: TMemberLeave[]) => {
  const decideLeave = vi.fn().mockResolvedValue(true);

  useAvailabilityMock.mockReturnValue({
    pendingLeaves,
    leaveTypes: [annual],
    fetchPending: vi.fn(),
    decideLeave,
  });
  useMemberMock.mockReturnValue({
    getUserDetails: (id: string) => ({ display_name: id === "ana" ? "Ana" : "Bob", email: `${id}@plane.so` }),
  });

  const { container } = render(
    <MemoryRouter initialEntries={["/acme/calendar/leave"]}>
      <Routes>
        <Route path=":workspaceSlug/calendar/leave" element={<ApprovalQueue />} />
      </Routes>
    </MemoryRouter>
  );

  return { decideLeave, container };
};

afterEach(cleanup);

describe("ApprovalQueue", () => {
  it("renders nothing at all when nobody is waiting", () => {
    const { container } = mount([]);

    // Not an empty panel saying zero. A spot that is usually blank stops being looked at,
    // which is the one thing an approval queue cannot afford.
    expect(container.textContent).toBe("");
  });

  it("counts what is waiting, so the number is readable without expanding anything", () => {
    mount([request(), request({ id: "leave-2", member: "bob" })]);

    expect(screen.getByText(/team_calendar.approvals.title \(2\)/)).toBeDefined();
  });

  it("carries the note the approver typed into the decision", async () => {
    const user = userEvent.setup();
    const { decideLeave } = mount([request()]);

    await user.type(screen.getByPlaceholderText("team_calendar.approvals.note"), "swap with Bob");
    await user.click(screen.getByRole("button", { name: /approve/ }));

    expect(decideLeave).toHaveBeenCalledWith("acme", "leave-1", "approve", "swap with Bob");
  });

  it("sends a rejection as a rejection, not an approval with a note", async () => {
    const user = userEvent.setup();
    const { decideLeave } = mount([request()]);

    await user.click(screen.getByRole("button", { name: /reject/ }));

    expect(decideLeave).toHaveBeenCalledWith("acme", "leave-1", "reject", "");
  });

  it("shows the reason when the API sent one, and nothing where it did not", () => {
    cleanup();
    mount([request({ reason: "moving house" })]);
    expect(screen.getByText("“moving house”")).toBeDefined();

    cleanup();
    // The API omits the key rather than nulling it for readers not entitled to it, so
    // there is nothing here to render — not even an empty pair of quotes.
    mount([request()]);
    expect(screen.queryByText(/“/)).toBeNull();
  });

  it("names the requester rather than showing their id", () => {
    mount([request()]);

    expect(screen.getByText("Ana")).toBeDefined();
  });

  it("shows a single date once, and a range as a range", () => {
    cleanup();
    const { container: single } = mount([request()]);
    expect(single.textContent).toContain("2026-08-12");
    expect(single.textContent).not.toContain("–");

    cleanup();
    const { container: range } = mount([request({ end_date: "2026-08-14" })]);
    expect(range.textContent).toContain("2026-08-12 – 2026-08-14");
  });
});
