/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { computedFn } from "mobx-utils";
import type { IssuePaginationOptions } from "@plane/types";
import type { IProjectIssuesFilter } from "@/store/issue/project";
import { ProjectIssuesFilter } from "@/store/issue/project";
import type { IIssueRootStore } from "@/store/issue/root.store";

export type IProjectEpicsFilter = IProjectIssuesFilter;

/**
 * The project work-item filters, scoped to work items whose type carries `is_epic`.
 *
 * Everything a user can filter, group or order by applies unchanged -- an epic list is the
 * work-item list with one more predicate, not a different list. The predicate is the `epic`
 * boolean rather than a type id because the id carrying the flag differs per workspace and
 * this store has no way to look it up.
 *
 * `leaf_only` is the one thing that cannot be inherited. It defaults to `true` for the
 * work-item list -- see `buildDisplayFilters` -- because that list answers "what is there to
 * do" and a node with children is a summary rather than a row you can pick up. An epic is
 * that summary, so carrying the default through would drop every epic anyone had broken
 * down: the demo project showed 1 epic of 5, the one nobody had added a feature to yet.
 * Pinned rather than merely defaulted, so that it holds however the filter record it shares
 * with the work-item list was last written; `EPIC_DISPLAY_FILTERS` drops the toggle from
 * Display to match, rather than offering one this pin would overrule.
 */
export class ProjectEpicsFilter extends ProjectIssuesFilter implements IProjectEpicsFilter {
  constructor(_rootStore: IIssueRootStore) {
    super(_rootStore);

    // root store
    this.rootIssueStore = _rootStore;

    // Wrapped rather than overridden. `getFilterParams` is an arrow-function property, so a
    // subclass field of the same name would shadow it with no route back through `super`,
    // and restating its two-line body here would drift from the parent the first time
    // pagination changed. Capturing it in the constructor works precisely because this
    // class declares no such field, so the binding still points at the parent's.
    const inherited = this.getFilterParams;
    this.getFilterParams = computedFn(
      (
        options: IssuePaginationOptions,
        projectId: string,
        cursor: string | undefined,
        groupId: string | undefined,
        subGroupId: string | undefined
      ) => ({
        ...inherited(options, projectId, cursor, groupId, subGroupId),
        epic: true,
        leaf_only: false,
      })
    );
  }

  /**
   * The epic list, not the work-item list.
   *
   * The parent clears and refetches whichever store its filters drive whenever a display
   * filter changes shape. Inheriting that unchanged pointed both at `projectIssues`, so
   * regrouping the epics page reloaded the work-item list and left the epics on screen
   * grouped by the setting they had a moment ago.
   */
  protected get issuesStore() {
    return this.rootIssueStore.projectEpics;
  }
}
