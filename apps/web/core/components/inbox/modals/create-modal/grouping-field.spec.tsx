/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { TWorkItemProperty } from "@plane/types";
import { IntakeGroupingField } from "./grouping-field";

afterEach(cleanup);

const definition = (overrides: Partial<TWorkItemProperty> = {}): TWorkItemProperty => ({
  id: "dimension",
  name: "合作客戶",
  description: "",
  kind: "multi_select",
  is_required: false,
  is_active: true,
  is_grouping_dimension: true,
  sort_order: 10,
  default_value: null,
  options: [
    { id: "o1", label: "Acme 物流", value: "acme", sort_order: 1000 },
    { id: "o2", label: "Globex 製造", value: "globex", sort_order: 2000 },
  ],
  type: null,
  project: "project",
  workspace: "workspace",
  created_at: "",
  updated_at: "",
  ...overrides,
});

describe("IntakeGroupingField", () => {
  // SCN-IA-03 / SCN-IA-04 / SCN-IA-05 all reach this component the same way: the caller
  // resolved no dimension, so the form must not grow a field.
  it("renders nothing without a dimension", () => {
    const { container } = render(<IntakeGroupingField definition={undefined} value={[]} onChange={vi.fn()} />);
    expect(container.innerHTML).toBe("");
  });

  // SCN-IA-01. The heading is the project's own word for the dimension; no name is
  // compiled into the product.
  it("labels the field with the property's own name", () => {
    render(<IntakeGroupingField definition={definition()} value={[]} onChange={vi.fn()} />);
    expect(screen.getByText("合作客戶")).toBeTruthy();
  });

  // SCN-IA-02
  it("reports the account the reporter picked", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<IntakeGroupingField definition={definition()} value={[]} onChange={onChange} />);

    await user.click(screen.getByRole("button"));
    await user.click(screen.getByText("Acme 物流"));

    expect(onChange).toHaveBeenLastCalledWith(["acme"]);
  });

  // SCN-IA-06
  it("shows the required marker and the error it was given", () => {
    render(
      <IntakeGroupingField
        definition={definition({ is_required: true })}
        value={[]}
        onChange={vi.fn()}
        error="This property is required."
      />
    );

    expect(screen.getByText("合作客戶").textContent).toContain("*");
    expect(screen.getByText("This property is required.")).toBeTruthy();
  });
});
