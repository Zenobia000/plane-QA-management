// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import type { TLeaveType } from "@plane/types";

const { useAvailabilityMock } = vi.hoisted(() => ({ useAvailabilityMock: vi.fn() }));

vi.mock("@/hooks/store/use-availability", () => ({ useAvailability: useAvailabilityMock }));

import { LeaveForm } from "./leave-form";

const annual: TLeaveType = {
  id: "type-annual",
  name: "Annual",
  colour: "#2E7D32",
  consumes_capacity: true,
  requires_approval: true,
  is_active: true,
  sort_order: 1,
};

const retired: TLeaveType = { ...annual, id: "type-retired", name: "Study leave", is_active: false };

const mount = (over: { leaveTypes?: TLeaveType[]; error?: string | null } = {}) => {
  const createLeave = vi.fn().mockResolvedValue(true);
  const onDone = vi.fn();

  useAvailabilityMock.mockReturnValue({
    leaveTypes: over.leaveTypes ?? [annual],
    createLeave,
    error: over.error ?? null,
  });

  render(
    <MemoryRouter initialEntries={["/acme/calendar/leave"]}>
      <Routes>
        <Route path=":workspaceSlug/calendar/leave" element={<LeaveForm onDone={onDone} />} />
      </Routes>
    </MemoryRouter>
  );

  return { createLeave, onDone };
};

/** `today` seeds both date fields, so the cases need a fixed one. */
beforeAll(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date("2026-08-07T00:00:00+00:00"));
});

afterAll(() => {
  vi.useRealTimers();
});

afterEach(cleanup);

describe("LeaveForm", () => {
  it("offers only leave types still in use", () => {
    mount({ leaveTypes: [annual, retired] });

    expect(screen.getByRole("option", { name: "Annual" })).toBeDefined();
    // Retired types stay in the record of who was away, but nobody should be able to book
    // a new absence against one.
    expect(screen.queryByRole("option", { name: "Study leave" })).toBeNull();
  });

  it("asks for a half day only while the absence is one day long", async () => {
    const user = userEvent.setup();
    mount();

    expect(screen.getByLabelText("team_calendar.form.part")).toBeDefined();

    // Half of what, over three days? The question has no answer, so it stops being asked.
    const to = screen.getByLabelText("team_calendar.form.to");
    await user.clear(to);
    await user.type(to, "2026-08-09");

    expect(screen.queryByLabelText("team_calendar.form.part")).toBeNull();
  });

  it("drags the end date along when the start passes it", async () => {
    const user = userEvent.setup();
    const { createLeave } = mount();

    const from = screen.getByLabelText("team_calendar.form.from");
    await user.clear(from);
    await user.type(from, "2026-08-20");

    await user.selectOptions(screen.getByLabelText("team_calendar.form.type"), annual.id);
    await user.click(screen.getByRole("button", { name: "team_calendar.form.submit" }));

    // A backwards range is refused by the server; correcting it here means nobody meets
    // an error for a date they never chose.
    expect(createLeave).toHaveBeenCalledWith(
      "acme",
      expect.objectContaining({ start_date: "2026-08-20", end_date: "2026-08-20" })
    );
  });

  it("sends whole days at both ends of a range, whatever the half-day picker last held", async () => {
    const user = userEvent.setup();
    const { createLeave } = mount();

    await user.selectOptions(screen.getByLabelText("team_calendar.form.part"), "morning");
    const to = screen.getByLabelText("team_calendar.form.to");
    await user.clear(to);
    await user.type(to, "2026-08-09");
    await user.selectOptions(screen.getByLabelText("team_calendar.form.type"), annual.id);
    await user.click(screen.getByRole("button", { name: "team_calendar.form.submit" }));

    expect(createLeave).toHaveBeenCalledWith(
      "acme",
      expect.objectContaining({ start_day_part: "full", end_day_part: "full" })
    );
  });

  it("will not submit until a leave type is chosen", async () => {
    const user = userEvent.setup();
    const { createLeave } = mount();

    await user.click(screen.getByRole("button", { name: "team_calendar.form.submit" }));

    expect(createLeave).not.toHaveBeenCalled();
  });

  it("stays open, with the dates still filled in, when the server refuses", async () => {
    const user = userEvent.setup();
    const { createLeave, onDone } = mount();

    createLeave.mockResolvedValueOnce(false);
    await user.selectOptions(screen.getByLabelText("team_calendar.form.type"), annual.id);
    await user.click(screen.getByRole("button", { name: "team_calendar.form.submit" }));

    // Closing here would report a refusal as a success and throw away the only copy of
    // what the person was trying to book.
    expect(onDone).not.toHaveBeenCalled();
    expect(screen.getByLabelText("team_calendar.form.from")).toHaveProperty("value", "2026-08-07");
  });

  it("closes once the absence is recorded", async () => {
    const user = userEvent.setup();
    const { onDone } = mount();

    await user.selectOptions(screen.getByLabelText("team_calendar.form.type"), annual.id);
    await user.click(screen.getByRole("button", { name: "team_calendar.form.submit" }));

    expect(onDone).toHaveBeenCalled();
  });

  it("says who will be able to read the reason", () => {
    mount();

    expect(screen.getByText("team_calendar.form.reason_privacy")).toBeDefined();
  });

  it("surfaces what the server refused", () => {
    mount({ error: "Leave overlaps an existing request" });

    expect(screen.getByText("Leave overlaps an existing request")).toBeDefined();
  });
});
