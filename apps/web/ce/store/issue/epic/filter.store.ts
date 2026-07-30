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
      })
    );
  }
}
