/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it, vi } from "vitest";
import type { TWorkItemProperty } from "@plane/types";
import { isGroupingValueMissing, persistGroupingValue } from "./grouping-value";

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
  options: [],
  type: null,
  project: "project",
  workspace: "workspace",
  created_at: "",
  updated_at: "",
  ...overrides,
});

const args = (value: unknown, property: TWorkItemProperty | undefined, setPropertyValue = vi.fn()) => ({
  definition: property,
  issueId: "issue-1",
  projectId: "project-1",
  service: { setPropertyValue },
  value,
  workspaceSlug: "acme",
});

describe("isGroupingValueMissing", () => {
  // SCN-IA-06
  it("is true for a required dimension with no value", () => {
    expect(isGroupingValueMissing(definition({ is_required: true }), [])).toBe(true);
    expect(isGroupingValueMissing(definition({ is_required: true }), "")).toBe(true);
    expect(isGroupingValueMissing(definition({ is_required: true }), undefined)).toBe(true);
  });

  it("is false once the required dimension has a value", () => {
    expect(isGroupingValueMissing(definition({ is_required: true }), ["acme"])).toBe(false);
  });

  it("is false for an optional dimension left empty", () => {
    expect(isGroupingValueMissing(definition(), [])).toBe(false);
  });

  it("is false when the form shows no dimension at all", () => {
    expect(isGroupingValueMissing(undefined, [])).toBe(false);
  });
});

describe("persistGroupingValue", () => {
  // SCN-IA-02
  it("writes the chosen value against the new work item", async () => {
    const setPropertyValue = vi.fn().mockResolvedValue({});
    const property = definition();

    await expect(persistGroupingValue(args(["acme"], property, setPropertyValue))).resolves.toBe("saved");
    expect(setPropertyValue).toHaveBeenCalledWith("acme", "project-1", "issue-1", "dimension", ["acme"]);
  });

  it("writes nothing when the form showed no dimension", async () => {
    const setPropertyValue = vi.fn();
    await expect(persistGroupingValue(args(["acme"], undefined, setPropertyValue))).resolves.toBe("skipped");
    expect(setPropertyValue).not.toHaveBeenCalled();
  });

  it("writes nothing when the reporter left it empty", async () => {
    const setPropertyValue = vi.fn();
    await expect(persistGroupingValue(args([], definition(), setPropertyValue))).resolves.toBe("skipped");
    expect(setPropertyValue).not.toHaveBeenCalled();
  });

  // SCN-IA-07. The work item exists either way; only the attribution is lost, and the
  // caller has to be able to tell the difference so it does not report a plain success.
  it("reports a failed write rather than throwing", async () => {
    const setPropertyValue = vi.fn().mockRejectedValue(new Error("403"));
    await expect(persistGroupingValue(args(["acme"], definition(), setPropertyValue))).resolves.toBe("failed");
  });
});
