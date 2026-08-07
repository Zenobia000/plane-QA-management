import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";
import type { TMemberSchedule, TOverlapResult } from "@plane/types";

const { useAvailabilityMock, useMemberMock } = vi.hoisted(() => ({
  useAvailabilityMock: vi.fn(),
  useMemberMock: vi.fn(),
}));

vi.mock("@/hooks/store/use-availability", () => ({ useAvailability: useAvailabilityMock }));
vi.mock("@/hooks/store/use-member", () => ({ useMember: useMemberMock }));

import { SlotFinder } from "./slot-finder";

const DAYS = ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07", "2026-08-08", "2026-08-09"];

const members: TMemberSchedule[] = [
  { member_id: "ana", timezone: "Asia/Taipei", calendar_id: "cal-tw", hours_per_day: 8, working: [], core: [] },
  { member_id: "bob", timezone: "Europe/Berlin", calendar_id: null, hours_per_day: 0, working: [], core: [] },
];

/** The window the backend contract test also asserts: 07:00-10:00 UTC on 2026-08-03. */
const result = (over: Partial<TOverlapResult> = {}): TOverlapResult => ({
  duration_minutes: 60,
  core: [],
  working: [{ start: "2026-08-03T07:00:00+00:00", end: "2026-08-03T10:00:00+00:00", minutes: 180 }],
  unknown_members: [],
  members_without_hours: [],
  ...over,
});

const render = (overlap: TOverlapResult | null, zone = "Asia/Taipei") => {
  useAvailabilityMock.mockReturnValue({ overlap, findOverlap: vi.fn(), clearOverlap: vi.fn() });
  useMemberMock.mockReturnValue({
    getUserDetails: (id: string) => ({ display_name: id === "ana" ? "Ana" : "Bob", email: `${id}@plane.so` }),
  });

  return renderToStaticMarkup(
    <MemoryRouter initialEntries={["/acme/calendar/schedule"]}>
      <Routes>
        <Route
          path=":workspaceSlug/calendar/schedule"
          element={<SlotFinder days={DAYS} zone={zone} members={members} />}
        />
      </Routes>
    </MemoryRouter>
  );
};

describe("SlotFinder", () => {
  it("shows no result section until a search has been run", () => {
    const markup = render(null);

    expect(markup).toContain("team_calendar.slot_finder.title");
    expect(markup).not.toContain("team_calendar.slot_finder.working");
    expect(markup).not.toContain("team_calendar.slot_finder.clear");
  });

  it("reads the window in the viewer's chosen zone, not the server's", () => {
    // Same instant, two readers. A meeting time in the wrong zone is worse than no answer,
    // because it looks like an answer.
    expect(render(result(), "Asia/Taipei")).toContain("15:00");
    expect(render(result(), "Europe/Berlin")).toContain("09:00");
  });

  it("names who has not declared hours instead of quietly shrinking the answer", () => {
    const markup = render(result({ members_without_hours: ["bob"] }));

    expect(markup).toContain("team_calendar.slot_finder.undeclared");
    expect(markup).toContain("Bob");
  });

  it("distinguishes no core overlap from no overlap at all", () => {
    // "Nobody shares core hours" and "nobody shares any hours" lead to different decisions:
    // the first is a meeting somebody stretches for, the second is not a meeting.
    const markup = render(result());

    expect(markup).toContain("team_calendar.slot_finder.no_core");
    expect(markup).not.toContain("team_calendar.slot_finder.no_working");
  });

  it("offers every member as a participant, including one with nothing declared", () => {
    const markup = render(null);

    expect(markup).toContain("Ana");
    expect(markup).toContain("Bob");
  });
});
