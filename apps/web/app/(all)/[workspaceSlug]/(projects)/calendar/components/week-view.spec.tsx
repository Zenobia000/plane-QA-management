import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";
import type { TAvailabilityCapabilities, TMemberSchedule } from "@plane/types";

const { useAvailabilityMock, useMemberMock } = vi.hoisted(() => ({
  useAvailabilityMock: vi.fn(),
  useMemberMock: vi.fn(),
}));

vi.mock("@/hooks/store/use-availability", () => ({ useAvailability: useAvailabilityMock }));
vi.mock("@/hooks/store/use-member", () => ({ useMember: useMemberMock }));

import { WeekView } from "./week-view";

const capability = (overlap: boolean): TAvailabilityCapabilities => ({
  enabled: true,
  stage: "reachable-hours",
  capabilities: { schedule: true, overlap, leave: false, allocation: false, capacity: false },
});

/** 2026-08-03 is a Monday. Taipei 09:00-18:00 is 01:00-10:00 UTC. */
const taipei: TMemberSchedule = {
  member_id: "ana",
  timezone: "Asia/Taipei",
  calendar_id: "cal-tw",
  hours_per_day: 8,
  working: [{ start: "2026-08-03T01:00:00+00:00", end: "2026-08-03T10:00:00+00:00", minutes: 540 }],
  core: [{ start: "2026-08-03T06:00:00+00:00", end: "2026-08-03T09:00:00+00:00", minutes: 180 }],
};

const undeclared: TMemberSchedule = {
  member_id: "bob",
  timezone: "Europe/Berlin",
  calendar_id: null,
  hours_per_day: 0,
  working: [],
  core: [],
};

const render = (members: TMemberSchedule[], overlap = false) => {
  useAvailabilityMock.mockReturnValue({
    schedule: { from: "2026-08-03", to: "2026-08-09", members },
    scheduleLoading: false,
    fetchSchedule: vi.fn(),
    capability: capability(overlap),
    overlap: null,
    findOverlap: vi.fn(),
    clearOverlap: vi.fn(),
  });
  useMemberMock.mockReturnValue({
    getUserDetails: (id: string) => ({ display_name: id === "ana" ? "Ana" : "Bob", email: `${id}@plane.so` }),
    workspace: { fetchWorkspaceMembers: vi.fn() },
  });

  return renderToStaticMarkup(
    <MemoryRouter initialEntries={["/acme/calendar/schedule"]}>
      <Routes>
        <Route path=":workspaceSlug/calendar/schedule" element={<WeekView />} />
      </Routes>
    </MemoryRouter>
  );
};

describe("WeekView", () => {
  it("names every member, including one who has declared nothing", () => {
    const markup = render([taipei, undeclared]);

    expect(markup).toContain("Ana");
    // Greyed out rather than dropped: seeing that Bob has said nothing is the useful part.
    expect(markup).toContain("Bob");
  });

  it("says so when a member has declared no hours", () => {
    const markup = render([undeclared]);

    expect(markup).toContain("team_calendar.schedule.not_declared");
  });

  it("offers the member's own zone in the viewer picker", () => {
    const markup = render([taipei]);

    expect(markup).toContain("Asia/Taipei");
  });

  it("hides the slot finder until the overlap capability is on", () => {
    expect(render([taipei], false)).not.toContain("team_calendar.slot_finder.title");
    expect(render([taipei], true)).toContain("team_calendar.slot_finder.title");
  });

  it("draws core hours as their own bar, not merged into the working bar", () => {
    // "I am at work" and "you may interrupt me" are different claims; one bar for both is
    // how the calendar stops being trusted.
    const markup = render([taipei]);

    expect(markup.match(/left:/g)?.length ?? 0).toBeGreaterThan(1);
  });
});
