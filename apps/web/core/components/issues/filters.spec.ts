/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import { ISSUE_STORE_TO_FILTERS_MAP } from "@plane/constants";
import { EIssuesStoreType } from "@plane/types";

/**
 * What `HeaderFilters` can put in the Display panel for a given page.
 *
 * The panel renders nothing at all when the lookup misses -- `DisplayFiltersSelection` reads
 * the options off this map and each of its sections is gated on the key being present -- so
 * a page absent from the map has a Display button that opens onto an empty popover. That is
 * how the epics page shipped, and it is why a grouping applied to it could not be undone.
 */
const optionsFor = (storeType: EIssuesStoreType, layout: string) =>
  ISSUE_STORE_TO_FILTERS_MAP[storeType]?.layoutOptions[layout];

describe("epics page display filters", () => {
  it("offers the same layouts the work-item list does", () => {
    const epicLayouts = Object.keys(ISSUE_STORE_TO_FILTERS_MAP[EIssuesStoreType.EPIC]?.layoutOptions ?? {});
    const workItemLayouts = Object.keys(ISSUE_STORE_TO_FILTERS_MAP[EIssuesStoreType.PROJECT]?.layoutOptions ?? {});

    expect(epicLayouts).toEqual(workItemLayouts);
    expect(epicLayouts.length).toBeGreaterThan(0);
  });

  it.each(["list", "spreadsheet"])("lets %s grouping be turned back off", (layout) => {
    // `null` is the "None" entry. Without it a user who grouped the page -- or who switched
    // to kanban, which writes `group_by: state` because a board has to have columns -- has
    // no way back to a flat list.
    expect(optionsFor(EIssuesStoreType.EPIC, layout)?.display_filters.group_by).toContain(null);
  });

  it.each(["list", "kanban", "calendar", "spreadsheet", "gantt_chart"])("fills the %s Display panel", (layout) => {
    const options = optionsFor(EIssuesStoreType.EPIC, layout);

    expect(options).toBeDefined();
    expect(options?.display_properties.length).toBeGreaterThan(0);
  });

  it("does not offer to group epics by their parent story", () => {
    // An epic is the top of the hierarchy, so every row would land in the same column.
    for (const layout of Object.keys(ISSUE_STORE_TO_FILTERS_MAP[EIssuesStoreType.EPIC]?.layoutOptions ?? {})) {
      expect(optionsFor(EIssuesStoreType.EPIC, layout)?.display_filters.group_by ?? []).not.toContain("parent");
    }
  });

  it("does not offer the leaf-only toggle", () => {
    // `ProjectEpicsFilter` pins `leaf_only: false`, so the toggle would report a state the
    // fetch ignores -- and an epic that has been broken down is what the page is for.
    for (const layout of Object.keys(ISSUE_STORE_TO_FILTERS_MAP[EIssuesStoreType.EPIC]?.layoutOptions ?? {})) {
      expect(optionsFor(EIssuesStoreType.EPIC, layout)?.extra_options.values ?? []).not.toContain("leaf_only");
    }
  });

  it("leaves the work-item list's own options untouched", () => {
    expect(optionsFor(EIssuesStoreType.PROJECT, "list")?.display_filters.group_by).toContain("parent");
    expect(optionsFor(EIssuesStoreType.PROJECT, "list")?.extra_options.values).toContain("leaf_only");
  });
});
