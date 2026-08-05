/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// @vitest-environment jsdom

import { useState } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { TRequirementKind } from "@plane/types";
import { RequirementKindDropdown } from "./requirement-kind";

afterEach(cleanup);

// The real `useTranslation` needs the i18n provider; the labels themselves are covered by the
// locale sync check, so the identity function keeps these cases about behaviour.
vi.mock("@plane/i18n", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

function Harness({
  initial,
  onChange,
  disabled,
}: {
  initial: TRequirementKind | null;
  onChange: (value: TRequirementKind) => void;
  disabled?: boolean;
}) {
  const [value, setValue] = useState<TRequirementKind | null>(initial);
  return (
    <RequirementKindDropdown
      value={value}
      disabled={disabled}
      onChange={(next) => {
        setValue(next);
        onChange(next);
      }}
    />
  );
}

const open = async (user: ReturnType<typeof userEvent.setup>) => user.click(screen.getByRole("button"));

describe("RequirementKindDropdown", () => {
  it("offers all three kinds, none included", async () => {
    const user = userEvent.setup();
    render(<Harness initial="none" onChange={vi.fn()} />);

    await open(user);

    // Scoped to the option list because the trigger repeats whichever kind is selected.
    const labels = screen.getAllByRole("option").map((option) => option.textContent);
    // `none` is a classification -- "states no requirement" -- and has to be reachable, not
    // just the state you are left in when you have not chosen.
    expect(labels).toHaveLength(3);
    expect(labels.some((label) => label?.includes("issue.requirement_kind.none"))).toBe(true);
    expect(labels.some((label) => label?.includes("issue.requirement_kind.functional"))).toBe(true);
    expect(labels.some((label) => label?.includes("issue.requirement_kind.quality"))).toBe(true);
  });

  it("reports the chosen kind", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Harness initial="none" onChange={onChange} />);

    await open(user);
    const quality = screen
      .getAllByRole("option")
      .find((option) => option.textContent?.includes("issue.requirement_kind.quality"));
    await user.click(quality!);

    expect(onChange).toHaveBeenLastCalledWith("quality");
  });

  it("shows the stored kind on the trigger", () => {
    render(<Harness initial="functional" onChange={vi.fn()} />);

    expect(screen.getByRole("button").textContent).toContain("issue.requirement_kind.functional");
  });

  // The column has no null, so a missing value is the same statement as `none` rather than a
  // separate "not yet classified" state. Rendering blank would invent one.
  it("falls back to none when the work item carries no value yet", () => {
    render(<Harness initial={null} onChange={vi.fn()} />);

    expect(screen.getByRole("button").textContent).toContain("issue.requirement_kind.none");
  });

  it("does not open when the work item is not editable", async () => {
    const user = userEvent.setup();
    render(<Harness initial="none" onChange={vi.fn()} disabled />);

    await open(user);

    expect(screen.queryAllByRole("option")).toHaveLength(0);
  });
});
