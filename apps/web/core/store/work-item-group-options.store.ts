/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { set } from "lodash-es";
import { action, observable, makeObservable, runInAction } from "mobx";
import { computedFn } from "mobx-utils";
// types
import { WorkItemGroupOptionService } from "@plane/services";
import type { TWorkItemParentGroupOption } from "@plane/types";

export interface IWorkItemGroupOptionsStore {
  // observables
  parentOptionsMap: Record<string, TWorkItemParentGroupOption[]>;
  // computed actions
  getParentOptions: (projectId: string) => TWorkItemParentGroupOption[] | undefined;
  // actions
  fetchParentOptions: (workspaceSlug: string, projectId: string) => Promise<TWorkItemParentGroupOption[] | undefined>;
}

/**
 * Column headings for grouping work items by parent.
 *
 * `getGroupByColumns` reads every other grouping's headings straight out of a store, because
 * every other grouping is a small set a project already loaded. This store exists so parent
 * can be read the same way instead of becoming the one dimension that needs its columns
 * threaded in from a component.
 *
 * Kept out of `useProjectIssueProperties`' `fetchAll` on purpose: states, labels, members and
 * cycles are needed to draw any work-item row at all, while these are needed only once
 * somebody chooses this grouping. Opening a project should not pay for a view most of them
 * will not select.
 */
export class WorkItemGroupOptionsStore implements IWorkItemGroupOptionsStore {
  parentOptionsMap: Record<string, TWorkItemParentGroupOption[]> = {};

  service: WorkItemGroupOptionService;

  constructor() {
    makeObservable(this, {
      parentOptionsMap: observable,
      fetchParentOptions: action,
    });
    this.service = new WorkItemGroupOptionService();
  }

  getParentOptions = computedFn((projectId: string) => this.parentOptionsMap[projectId]);

  fetchParentOptions = async (workspaceSlug: string, projectId: string) => {
    try {
      const options = await this.service.listParentOptions(workspaceSlug, projectId);
      runInAction(() => {
        set(this.parentOptionsMap, [projectId], options);
      });
      return options;
    } catch (error) {
      // Leave the previous list in place. Headings that briefly outlive a failed refresh are
      // still the right headings; blanking them would empty the page over a dropped request.
      console.error("Failed to fetch parent group options", error);
      return undefined;
    }
  };
}
