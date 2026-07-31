/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

// @vitest-environment jsdom

import { useState } from "react";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { TWorkItemProperty, TWorkItemPropertyKind } from "@plane/types";
import { WorkItemPropertyField } from "./property-field";

afterEach(cleanup);

const definition = (kind: TWorkItemPropertyKind): TWorkItemProperty => ({
  id: "prop-1",
  name: "Impacted areas",
  description: "",
  kind,
  is_required: false,
  is_active: true,
  sort_order: 10,
  default_value: null,
  options: [
    { id: "o1", label: "API", value: "api", sort_order: 10 },
    { id: "o2", label: "Web", value: "web", sort_order: 20 },
    { id: "o3", label: "Mobile", value: "mobile", sort_order: 30 },
  ],
  project: "project-1",
  workspace: "workspace-1",
  created_at: "",
  updated_at: "",
});

/** The field is controlled, so accumulating a multi-select needs a real value holder. */
function Harness({ kind, onChange }: { kind: TWorkItemPropertyKind; onChange: (value: unknown) => void }) {
  const [value, setValue] = useState<unknown>(kind === "multi_select" ? [] : null);
  return (
    <WorkItemPropertyField
      definition={definition(kind)}
      value={value}
      onChange={(next) => {
        setValue(next);
        onChange(next);
      }}
    />
  );
}

const openDropdown = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(screen.getByRole("button"));
};

describe("WorkItemPropertyField multi_select", () => {
  it("renders a dropdown trigger rather than a native multiple listbox", () => {
    render(<Harness kind="multi_select" onChange={vi.fn()} />);

    expect(document.querySelector("select[multiple]")).toBeNull();
    const trigger = screen.getByRole("button");
    expect(trigger.textContent).toContain("Select options");
    // Options only exist once the dropdown is opened.
    expect(screen.queryByText("API")).toBeNull();
  });

  it("accumulates values as options are ticked, and untick removes one", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Harness kind="multi_select" onChange={onChange} />);

    await openDropdown(user);
    await user.click(screen.getByText("API"));
    expect(onChange).toHaveBeenLastCalledWith(["api"]);

    await user.click(screen.getByText("Mobile"));
    expect(onChange).toHaveBeenLastCalledWith(["api", "mobile"]);

    await user.click(screen.getByText("API"));
    expect(onChange).toHaveBeenLastCalledWith(["mobile"]);
  });

  it("shows a ticked checkbox and the selected labels for what is chosen", async () => {
    const user = userEvent.setup();
    render(<Harness kind="multi_select" onChange={vi.fn()} />);

    await openDropdown(user);
    await user.click(screen.getByText("API"));

    const checkboxes = screen.getAllByRole("checkbox") as HTMLInputElement[];
    expect(checkboxes.map((box) => box.checked)).toEqual([true, false, false]);
    expect(screen.getByRole("button").textContent).toContain("API");
  });
});

describe("WorkItemPropertyField select", () => {
  it("reports the chosen option and clears through the No value entry", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Harness kind="select" onChange={onChange} />);

    expect(document.querySelector("select")).toBeNull();
    expect(screen.getByRole("button").textContent).toContain("Select an option");

    await openDropdown(user);
    await user.click(screen.getByText("Web"));
    expect(onChange).toHaveBeenLastCalledWith("web");
    expect(screen.getByRole("button").textContent).toContain("Web");

    await openDropdown(user);
    await user.click(screen.getByText("No value"));
    expect(onChange).toHaveBeenLastCalledWith(null);
    expect(screen.getByRole("button").textContent).toContain("Select an option");
  });

  it("filters the option list through the search box", async () => {
    const user = userEvent.setup();
    render(<Harness kind="select" onChange={vi.fn()} />);

    await openDropdown(user);
    await user.type(screen.getByPlaceholderText("Search"), "mob");

    const list = screen.getByRole("listbox");
    expect(within(list).getByText("Mobile")).toBeTruthy();
    expect(within(list).queryByText("API")).toBeNull();
  });
});

describe("WorkItemPropertyField other kinds", () => {
  it("still renders a plain input for text properties", () => {
    render(<WorkItemPropertyField definition={definition("text")} value="hello" onChange={vi.fn()} />);

    const input = screen.getByDisplayValue("hello");
    expect(input.tagName).toBe("INPUT");
  });
});
