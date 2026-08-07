import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";

const { useAvailabilityMock, useMemberMock, useUserPermissionsMock, useProjectMock } = vi.hoisted(() => ({
  useAvailabilityMock: vi.fn(),
  useMemberMock: vi.fn(),
  useUserPermissionsMock: vi.fn(),
  useProjectMock: vi.fn(),
}));

vi.mock("@/hooks/store/use-availability", () => ({ useAvailability: useAvailabilityMock }));
vi.mock("@/hooks/store/use-member", () => ({ useMember: useMemberMock }));
vi.mock("@/hooks/store/user", () => ({ useUserPermissions: useUserPermissionsMock, useUser: vi.fn() }));
vi.mock("@/hooks/store/use-project", () => ({ useProject: useProjectMock }));

import { ApprovalQueue } from "./approval-queue";
import { AllocationMatrix } from "./allocation-matrix";

const render = (node: React.ReactElement) =>
  renderToStaticMarkup(
    <MemoryRouter initialEntries={["/acme/calendar/x"]}>
      <Routes>
        <Route path=":workspaceSlug/calendar/x" element={node} />
      </Routes>
    </MemoryRouter>
  );

const members = { getUserDetails: (id: string) => ({ display_name: id, email: `${id}@x` }) };

describe("ApprovalQueue — a note belongs to one request", () => {
  it("renders a note input per pending request, not one shared below the list", () => {
    useAvailabilityMock.mockReturnValue({
      pendingLeaves: [
        { id: "a", member: "ana", leave_type: "t", start_date: "2026-08-03", end_date: "2026-08-03" },
        { id: "b", member: "bob", leave_type: "t", start_date: "2026-08-04", end_date: "2026-08-04" },
      ],
      leaveTypes: [{ id: "t", name: "Annual" }],
      fetchPending: vi.fn(),
      decideLeave: vi.fn(),
    });
    useMemberMock.mockReturnValue(members);

    const markup = render(<ApprovalQueue />);

    // Two requests, two inputs. One shared box meant typing a reason for Bob and
    // attaching it to Ana.
    expect(markup.match(/<input/g)).toHaveLength(2);
  });

  it("renders nothing when the queue is empty", () => {
    useAvailabilityMock.mockReturnValue({
      pendingLeaves: [],
      leaveTypes: [],
      fetchPending: vi.fn(),
      decideLeave: vi.fn(),
    });
    useMemberMock.mockReturnValue(members);

    expect(render(<ApprovalQueue />)).toBe("");
  });
});

describe("AllocationMatrix — cells show what the server holds", () => {
  it("renders the server's percentage as a controlled value", () => {
    useAvailabilityMock.mockReturnValue({
      allocations: {
        allocations: [{ member_id: "ana", project_id: "alpha", allocation_percent: 60 }],
        totals: { ana: 60 },
      },
      fetchAllocations: vi.fn(),
      setAllocation: vi.fn(),
      error: null,
    });
    useMemberMock.mockReturnValue({
      ...members,
      workspace: { fetchWorkspaceMembers: vi.fn(), workspaceMemberIds: ["ana"] },
    });
    useProjectMock.mockReturnValue({ workspaceProjectIds: ["alpha"], getProjectById: () => ({ name: "Alpha" }) });
    useUserPermissionsMock.mockReturnValue({ allowPermissions: () => true });

    const markup = render(<AllocationMatrix />);

    // `value`, not `defaultValue`: an uncontrolled cell kept a number the server refused
    // while the total column showed the server's, displaying a split that was never saved.
    expect(markup).toContain('value="60"');
    expect(markup).toContain("60%");
  });
});
