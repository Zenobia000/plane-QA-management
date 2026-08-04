/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * The page row's "⋯" menu, checked against the actions that actually exist.
 *
 * `PageActions` renders only the keys named in `optionsOrder` -- it maps that array over
 * the menu items and drops anything not listed. So an action can be fully implemented,
 * wired and permission-gated, and still be invisible because one caller forgot to name it.
 *
 * That is exactly what happened to `add-sub-page`: present in the editor toolbar's order,
 * absent from this one. A folder in this product is a page with children, so that omission
 * left the Pages list with a single entry point for building one -- a "+" held at
 * `opacity-0` until the row is hovered. The feature looked missing because it was
 * unreachable by anyone who did not hover the right twenty pixels.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const read = (relativePath: string) => readFileSync(join(__dirname, relativePath), "utf8");

/** The `optionsOrder={[...]}` literal, as the list of keys it names. */
const optionsOrder = (source: string): string[] => {
  const match = source.match(/optionsOrder=\{\[([\s\S]*?)\]\}/);
  if (!match) throw new Error("no optionsOrder literal found");
  return [...match[1].matchAll(/"([a-z-]+)"/g)].map((m) => m[1]);
};

describe("page row quick actions", () => {
  it("offers a way to create a sub-page", () => {
    // The only discoverable route to a folder from the list.
    expect(optionsOrder(read("./block-item-action.tsx"))).toContain("add-sub-page");
  });

  it("names only keys the actions component knows how to render", () => {
    const declared = read("../dropdowns/actions.tsx");
    for (const key of optionsOrder(read("./block-item-action.tsx"))) {
      expect(declared, `"${key}" is ordered but never defined`).toContain(`key: "${key}"`);
    }
  });
});
