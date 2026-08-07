/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { IIntakeState } from "@plane/types";

const fetchProjectIntakeState = vi.fn();
const getProjectIntakeStateIds = vi.fn();
const getIntakeStateById = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ workspaceSlug: "acme" }),
}));

vi.mock("@/hooks/store/use-project-state", () => ({
  useProjectState: () => ({ fetchProjectIntakeState, getProjectIntakeStateIds, getIntakeStateById }),
}));

const { IntakeStateDropdown } = await import("./dropdown");

const triage = {
  id: "triage-1",
  name: "Triage",
  color: "#4E5355",
  group: "triage",
  default: false,
  project_id: "project-1",
} as unknown as IIntakeState;

afterEach(cleanup);

beforeEach(() => {
  getProjectIntakeStateIds.mockReturnValue(undefined);
  getIntakeStateById.mockReturnValue(undefined);
});

/** The variant the intake detail panel renders it with, so the button carries its text. */
const renderDropdown = (overrides: { disabled?: boolean } = {}) =>
  render(
    <IntakeStateDropdown
      value="triage-1"
      projectId="project-1"
      onChange={vi.fn()}
      buttonVariant="transparent-with-text"
      {...overrides}
    />
  );

describe("IntakeStateDropdown when read-only", () => {
  // SCN-IA-08. The intake detail panel renders this disabled, so it never opens -- and
  // loading only on open left it showing the placeholder for every item that had a state.
  it("loads the intake state on mount instead of waiting to be opened", () => {
    renderDropdown({ disabled: true });

    expect(fetchProjectIntakeState).toHaveBeenCalledWith("acme", "project-1");
  });

  it("shows the state's own name once it is loaded, not the placeholder", () => {
    getProjectIntakeStateIds.mockReturnValue(["triage-1"]);
    getIntakeStateById.mockReturnValue(triage);

    renderDropdown({ disabled: true });

    expect(screen.getByText("Triage")).toBeTruthy();
    // `t()` returns the key under vitest, so the placeholder would read as "state".
    expect(screen.queryByText("state")).toBeNull();
  });

  it("does not fetch again once the project's states are known", () => {
    getProjectIntakeStateIds.mockReturnValue(["triage-1"]);
    getIntakeStateById.mockReturnValue(triage);

    renderDropdown({ disabled: true });

    expect(fetchProjectIntakeState).not.toHaveBeenCalled();
  });

  it("leaves an editable dropdown to load when it is opened", () => {
    renderDropdown();

    expect(fetchProjectIntakeState).not.toHaveBeenCalled();
  });
});
