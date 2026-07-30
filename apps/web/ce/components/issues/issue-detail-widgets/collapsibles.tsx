/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useState } from "react";
// plane types
import { ProjectOverviewService } from "@plane/services";
import type { TEntityUpdate, TIssueServiceType, TUpdateStatus, TWorkItemWidgets } from "@plane/types";
import { UpdatesPanel } from "@/components/updates";

const overviewService = new ProjectOverviewService();

export type TWorkItemAdditionalWidgetCollapsiblesProps = {
  disabled: boolean;
  hideWidgets: TWorkItemWidgets[];
  issueServiceType: TIssueServiceType;
  projectId: string;
  workItemId: string;
  workspaceSlug: string;
};

/**
 * The work item's status thread.
 *
 * The same model and the same component the project overview uses, with a different
 * `entity_name`. Updates started as an epic-only feature upstream and were extended to
 * every work item type afterwards; building one model for both is the same conclusion
 * reached before rather than after. See ADR 0005.
 */
export function WorkItemAdditionalWidgetCollapsibles(props: TWorkItemAdditionalWidgetCollapsiblesProps) {
  const { disabled, projectId, workItemId, workspaceSlug } = props;
  const [updates, setUpdates] = useState<TEntityUpdate[]>([]);

  const load = useCallback(async () => {
    if (!workspaceSlug || !projectId || !workItemId) return;
    try {
      setUpdates(await overviewService.listUpdates(workspaceSlug, projectId, "work_item", workItemId));
    } catch {
      setUpdates([]);
    }
  }, [workspaceSlug, projectId, workItemId]);

  useEffect(() => {
    void load();
  }, [load]);

  const postUpdate = async (status: TUpdateStatus, description: string) => {
    await overviewService.createUpdate(workspaceSlug, projectId, {
      entity_name: "work_item",
      entity_identifier: workItemId,
      status,
      description,
    });
    await load();
  };

  const loadReplies = async (updateId: string) =>
    overviewService.listReplies(workspaceSlug, projectId, updateId, "work_item", workItemId);

  const postReply = async (parentId: string, description: string) => {
    await overviewService.createUpdate(workspaceSlug, projectId, {
      entity_name: "work_item",
      entity_identifier: workItemId,
      // A reply carries its parent's verdict rather than restating one of its own.
      status: updates.find((update) => update.id === parentId)?.status ?? "on_track",
      description,
      parent: parentId,
    });
    await load();
  };

  return (
    <div className="pt-3">
      <UpdatesPanel
        entityName="work_item"
        updates={updates}
        disabled={disabled}
        onPost={postUpdate}
        onLoadReplies={loadReplies}
        onReply={postReply}
      />
    </div>
  );
}
