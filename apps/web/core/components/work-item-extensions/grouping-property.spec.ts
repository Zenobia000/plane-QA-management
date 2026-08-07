/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import type { TWorkItemProperty } from "@plane/types";
import { intakeGroupingProperty } from "./grouping-property";

const property = (overrides: Partial<TWorkItemProperty>): TWorkItemProperty => ({
  id: "prop",
  name: "Property",
  description: "",
  kind: "multi_select",
  is_required: false,
  is_active: true,
  is_grouping_dimension: false,
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

const dimension = (overrides: Partial<TWorkItemProperty> = {}) =>
  property({ id: "dimension", name: "合作客戶", is_grouping_dimension: true, ...overrides });

describe("intakeGroupingProperty", () => {
  // SCN-IA-01
  it("returns the project's grouping dimension", () => {
    const definitions = [property({ id: "other" }), dimension()];
    expect(intakeGroupingProperty(definitions, true)?.id).toBe("dimension");
  });

  // SCN-IA-04
  it("returns nothing when no property is marked as the grouping dimension", () => {
    expect(intakeGroupingProperty([property({ id: "other" })], true)).toBeUndefined();
  });

  // SCN-IA-03. Writing a value needs MEMBER; filing an intake item only needs GUEST. A
  // field the caller cannot save is worse than no field -- it looks filled in and is not.
  it("returns nothing when the caller may not write property values", () => {
    expect(intakeGroupingProperty([dimension()], false)).toBeUndefined();
  });

  // SCN-IA-05. Intake creates a work item with no type, and the value endpoint refuses a
  // property narrowed to a type the item does not have.
  it("returns nothing when the dimension is narrowed to a work item type", () => {
    expect(intakeGroupingProperty([dimension({ type: "bug-type" })], true)).toBeUndefined();
  });

  it("ignores an inactive dimension", () => {
    expect(intakeGroupingProperty([dimension({ is_active: false })], true)).toBeUndefined();
  });

  it("returns nothing before the definitions have loaded", () => {
    expect(intakeGroupingProperty(undefined, true)).toBeUndefined();
  });
});
