/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useContext, useEffect } from "react";
// types
import type { TIssueGroupByOptions } from "@plane/types";
// mobx store
import { StoreContext } from "@/lib/store-context";
// store
import type { IWorkItemGroupOptionsStore } from "@/store/work-item-group-options.store";

export const useWorkItemGroupOptions = (): IWorkItemGroupOptionsStore => {
  const context = useContext(StoreContext);
  if (context === undefined) throw new Error("useWorkItemGroupOptions must be used within StoreProvider");
  return context.workItemGroupOptions;
};

/**
 * Load the story headings a layout needs, and only when it needs them.
 *
 * Grouping is the trigger rather than project entry: the request costs nothing to skip for
 * the views that group by state or priority, which is most of them. A layout that can group
 * by parent calls this; a layout that cannot does not have to know the store exists.
 */
export const useParentGroupOptions = (
  workspaceSlug: string | undefined,
  projectId: string | undefined,
  groupBy: TIssueGroupByOptions | undefined
) => {
  const { fetchParentOptions } = useWorkItemGroupOptions();

  useEffect(() => {
    if (groupBy !== "parent" || !workspaceSlug || !projectId) return;
    fetchParentOptions(workspaceSlug, projectId);
  }, [fetchParentOptions, groupBy, projectId, workspaceSlug]);
};
