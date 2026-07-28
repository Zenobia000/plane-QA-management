/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { describe, expect, it } from "vitest";
import { parsePropertyOptions } from "./settings";

describe("parsePropertyOptions", () => {
  it("creates stable unique values and preserves labels", () => {
    expect(parsePropertyOptions("Ready, ready, 待處理")).toEqual([
      { label: "Ready", value: "ready", sort_order: 10 },
      { label: "ready", value: "ready_2", sort_order: 20 },
      { label: "待處理", value: "option_3", sort_order: 30 },
    ]);
  });

  it("drops empty comma-separated options", () => {
    expect(parsePropertyOptions("Alpha, , Beta,")).toHaveLength(2);
  });
});
