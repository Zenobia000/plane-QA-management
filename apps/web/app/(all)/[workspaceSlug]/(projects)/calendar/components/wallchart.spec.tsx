import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import type { TLeaveType, TMemberLeave, TTeamEvent } from "@plane/types";

const { useAvailabilityMock, useMemberMock } = vi.hoisted(() => ({
  useAvailabilityMock: vi.fn(),
  useMemberMock: vi.fn(),
}));

vi.mock("@/hooks/store/use-availability", () => ({ useAvailability: useAvailabilityMock }));
vi.mock("@/hooks/store/use-member", () => ({ useMember: useMemberMock }));

import { Wallchart } from "./wallchart";

const annual: TLeaveType = {
  id: "type-annual",
  name: "Annual",
  colour: "#2E7D32",
  consumes_capacity: true,
  requires_approval: true,
  is_active: true,
  sort_order: 1,
};

const remote: TLeaveType = {
  ...annual,
  id: "type-remote",
  name: "Remote",
  colour: "#0288D1",
  consumes_capacity: false,
};

const leave = (over: Partial<TMemberLeave> = {}): TMemberLeave => ({
  id: "leave-1",
  member: "ana",
  leave_type: annual.id,
  start_date: "2026-08-12",
  end_date: "2026-08-12",
  start_day_part: "full",
  end_day_part: "full",
  status: "approved",
  decided_by: "admin",
  decided_at: "2026-08-07T00:00:00+00:00",
  ...over,
});

const render = (over: { leaves?: TMemberLeave[]; events?: TTeamEvent[]; leaveTypes?: TLeaveType[] } = {}) => {
  useAvailabilityMock.mockReturnValue({
    leaves: over.leaves ?? [],
    leaveTypes: over.leaveTypes ?? [annual],
    events: over.events ?? [],
    pendingLeaves: [],
    fetchMonth: vi.fn(),
    fetchPending: vi.fn(),
    decideLeave: vi.fn(),
    cancelLeave: vi.fn(),
  });
  useMemberMock.mockReturnValue({
    getUserDetails: (id: string) => ({ display_name: id === "ana" ? "Ana" : "Bob", email: `${id}@plane.so` }),
    workspace: { fetchWorkspaceMembers: vi.fn(), workspaceMemberIds: ["ana", "bob"] },
  });

  return renderToStaticMarkup(
    <MemoryRouter initialEntries={["/acme/calendar/leave"]}>
      <Routes>
        <Route path=":workspaceSlug/calendar/leave" element={<Wallchart />} />
      </Routes>
    </MemoryRouter>
  );
};

/** The month grid is built from "today", so the fixtures need a fixed one to land in. */
beforeAll(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-08-07T00:00:00+00:00"));
});

afterAll(() => {
  vi.useRealTimers();
});

describe("Wallchart", () => {
  it("gives every member a row, including one who is never away", () => {
    const markup = render({ leaves: [leave()] });

    expect(markup).toContain("Ana");
    // Bob has no leave at all. A wallchart that only lists the absent cannot be read as
    // "who is around", which is the question people bring to it.
    expect(markup).toContain("Bob");
  });

  it("paints the block in the leave type's own colour", () => {
    expect(render({ leaves: [leave()] })).toContain("#2E7D32");
  });

  it("draws a half day as half a block", () => {
    const full = render({ leaves: [leave()] });
    const half = render({ leaves: [leave({ start_day_part: "morning", end_day_part: "morning" })] });

    expect(full).not.toContain("polygon");
    expect(half).toContain("polygon");
  });

  it("fades a request nobody has decided yet", () => {
    // An approved absence and a requested one are different promises. Drawn identically,
    // the wallchart would report plans as facts.
    expect(render({ leaves: [leave({ status: "pending" })] })).toContain("opacity:0.45");
    expect(render({ leaves: [leave({ status: "approved" })] })).not.toContain("opacity:0.45");
  });

  it("spans a range across every day it covers", () => {
    const markup = render({ leaves: [leave({ start_date: "2026-08-12", end_date: "2026-08-14" })] });

    expect(markup.match(/#2E7D32/g)?.length ?? 0).toBe(4); // three days plus the legend swatch
  });

  it("marks in the legend which absences still leave somebody working", () => {
    const markup = render({ leaveTypes: [annual, remote] });

    expect(markup).toContain("team_calendar.wallchart.still_working");
  });

  it("adds the events row only when there are events", () => {
    expect(render()).not.toContain("team_calendar.wallchart.events");
    expect(
      render({
        events: [
          {
            id: "event-1",
            project: null,
            title: "Offsite",
            description: "",
            start_date: "2026-08-20",
            end_date: "2026-08-21",
            start_day_part: "full",
            end_day_part: "full",
            colour: "#8E24AA",
            consumes_capacity: true,
            audience: "all_members",
            attendee_ids: [],
          },
        ],
      })
    ).toContain("team_calendar.wallchart.events");
  });
});
