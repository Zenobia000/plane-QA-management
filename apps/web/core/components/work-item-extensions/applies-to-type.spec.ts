/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import type { TWorkItemProperty } from "@plane/types";
import { propertiesForType } from "./applies-to-type";

const property = (overrides: Partial<TWorkItemProperty>): TWorkItemProperty => ({
  id: "prop",
  name: "Property",
  description: "",
  kind: "text",
  is_required: false,
  is_active: true,
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

describe("propertiesForType", () => {
  it("keeps an untyped property for every type", () => {
    const untyped = property({ id: "untyped" });
    expect(propertiesForType([untyped], "bug-type").map((item) => item.id)).toEqual(["untyped"]);
    expect(propertiesForType([untyped], "epic-type").map((item) => item.id)).toEqual(["untyped"]);
  });

  it("keeps an untyped property when the item has no type at all", () => {
    // Projects with work item types switched off have every item untyped, and their
    // project-wide properties still have to render.
    expect(propertiesForType([property({ id: "untyped" })], null).map((item) => item.id)).toEqual(["untyped"]);
  });

  it("drops a property narrowed to a different type", () => {
    const severity = property({ id: "severity", type: "bug-type" });
    expect(propertiesForType([severity], "epic-type")).toEqual([]);
  });

  it("keeps a property narrowed to the item's own type", () => {
    const severity = property({ id: "severity", type: "bug-type" });
    expect(propertiesForType([severity], "bug-type").map((item) => item.id)).toEqual(["severity"]);
  });

  it("drops a narrowed property when the item has no type", () => {
    // Not merely absent -- an untyped item matches no narrowed property, and treating
    // null as a wildcard would ask for a field the API then refuses.
    expect(propertiesForType([property({ id: "severity", type: "bug-type" })], null)).toEqual([]);
  });

  it("still drops inactive properties", () => {
    const retired = property({ id: "retired", is_active: false });
    expect(propertiesForType([retired], "bug-type")).toEqual([]);
  });

  it("tolerates definitions not having loaded yet", () => {
    expect(propertiesForType(undefined, "bug-type")).toEqual([]);
  });
});
