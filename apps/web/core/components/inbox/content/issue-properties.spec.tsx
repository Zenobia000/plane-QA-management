/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EUserPermissions } from "@plane/constants";
import type { TIssue } from "@plane/types";
import type { TIssueOperations } from "@/components/issues/issue-detail";

/**
 * The dropdowns in this panel each reach for a different store. They are not what these
 * cases are about -- the question here is whether the custom property block is rendered
 * at all, and with what editability -- so they are stubbed and the block is captured.
 */
const additionalProperties = vi.fn();

vi.mock("@/plane-web/components/issues/issue-details/additional-properties", () => ({
  WorkItemAdditionalSidebarProperties: (props: Record<string, unknown>) => {
    additionalProperties(props);
    return <div data-testid="additional-properties" />;
  },
}));

const stub = (testId: string) => () => <div data-testid={testId} />;

vi.mock("@/components/dropdowns/date", () => ({ DateDropdown: stub("date") }));
vi.mock("@/components/dropdowns/member/dropdown", () => ({ MemberDropdown: stub("member") }));
vi.mock("@/components/dropdowns/priority", () => ({ PriorityDropdown: stub("priority") }));
vi.mock("@/components/dropdowns/state/dropdown", () => ({ StateDropdown: stub("state") }));
vi.mock("@/components/dropdowns/intake-state/dropdown", () => ({ IntakeStateDropdown: stub("intake-state") }));
vi.mock("@/components/issues/issue-detail/label", () => ({ IssueLabel: stub("label") }));
vi.mock("@/hooks/store/use-project", () => ({ useProject: () => ({ currentProjectDetails: { identifier: "DEMO" } }) }));
vi.mock("@/hooks/use-app-router", () => ({ useAppRouter: () => ({ push: vi.fn() }) }));

const allowPermissions = vi.fn();
vi.mock("@/hooks/store/user", () => ({ useUserPermissions: () => ({ allowPermissions }) }));

const { InboxIssueContentProperties } = await import("./issue-properties");

const issue = { id: "issue-1", state_id: "triage-1", type_id: null } as unknown as Partial<TIssue>;

const renderPanel = (isEditable: boolean) =>
  render(
    <InboxIssueContentProperties
      workspaceSlug="acme"
      projectId="project-1"
      issue={issue}
      issueOperations={{ update: vi.fn() } as unknown as TIssueOperations}
      isEditable={isEditable}
      duplicateIssueDetails={undefined}
      isIntakeAccepted={false}
    />
  );

afterEach(cleanup);

beforeEach(() => {
  allowPermissions.mockReturnValue(true);
});

describe("InboxIssueContentProperties custom properties", () => {
  // SCN-IA-10. Before this, the only way to set the property the overview groups by was to
  // accept the item and reopen it from the work item list.
  it("renders the project's custom properties on an item still in triage", () => {
    renderPanel(true);

    expect(screen.getByTestId("additional-properties")).toBeTruthy();
    expect(additionalProperties).toHaveBeenCalledWith(
      expect.objectContaining({ workItemId: "issue-1", projectId: "project-1", workspaceSlug: "acme" })
    );
  });

  it("passes the item's own type through, so a narrowed property is not asked for", () => {
    renderPanel(true);

    expect(additionalProperties).toHaveBeenCalledWith(expect.objectContaining({ workItemTypeId: null }));
  });

  // SCN-IA-11. This panel's isEditable also admits the item's creator, and a creator can
  // be a GUEST -- who may file an intake item but may not write a property value.
  it("is read-only for someone who may edit the item but not write property values", () => {
    allowPermissions.mockReturnValue(false);
    renderPanel(true);

    expect(additionalProperties).toHaveBeenCalledWith(expect.objectContaining({ isEditable: false }));
  });

  it("is read-only when the panel itself is read-only", () => {
    renderPanel(false);

    expect(additionalProperties).toHaveBeenCalledWith(expect.objectContaining({ isEditable: false }));
  });

  it("is editable for a member with edit rights on the item", () => {
    renderPanel(true);

    expect(additionalProperties).toHaveBeenCalledWith(expect.objectContaining({ isEditable: true }));
  });

  it("asks for the roles the property value endpoint requires", () => {
    renderPanel(true);

    expect(allowPermissions).toHaveBeenCalledWith(
      [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
      expect.anything(),
      "acme",
      "project-1"
    );
  });
});
