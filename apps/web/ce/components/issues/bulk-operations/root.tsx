/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "react-router";
import { X } from "lucide-react";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import { IssueBulkOperationsService } from "@plane/services";
import type { TIssuePriorities } from "@plane/types";
import { cn } from "@plane/utils";
// hooks
import { useMultipleSelectStore } from "@/hooks/store/use-multiple-select-store";
import { useProjectState } from "@/hooks/store/use-project-state";
import type { TSelectionHelper } from "@/hooks/use-multiple-select";

const bulkService = new IssueBulkOperationsService();

const PRIORITIES: TIssuePriorities[] = ["urgent", "high", "medium", "low", "none"];

const controlClass =
  "h-7 rounded border border-subtle bg-surface-1 px-2 text-12 text-primary outline-none focus:border-accent-strong disabled:opacity-50";

type Props = {
  className?: string;
  selectionHelpers: TSelectionHelper;
};

/**
 * The toolbar that appears once work items are selected.
 *
 * Only the properties one value can sensibly be applied to a whole selection are here --
 * state and priority. Name, description, parent and type are per-item by nature, and the
 * endpoint refuses them rather than letting a toolbar retitle fifty items alike.
 */
export const IssueBulkOperationsRoot = observer(function IssueBulkOperationsRoot(props: Props) {
  const { className, selectionHelpers } = props;
  const { workspaceSlug, projectId } = useParams();
  const { isSelectionActive, selectedEntityIds } = useMultipleSelectStore();
  const { projectStates } = useProjectState();
  const [busy, setBusy] = useState(false);

  const slug = workspaceSlug?.toString();
  const id = projectId?.toString();

  if (!isSelectionActive || selectionHelpers.isSelectionDisabled) return null;

  const apply = async (properties: Record<string, unknown>) => {
    if (!slug || !id || !selectedEntityIds.length) return;
    setBusy(true);
    try {
      const { updated } = await bulkService.update(slug, id, selectedEntityIds, properties);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Updated",
        message: `${updated} work ${updated === 1 ? "item" : "items"} changed.`,
      });
      selectionHelpers.handleClearSelection();
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: "Could not update the selection." });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={cn("sticky bottom-0 left-0 z-[2] grid place-items-center px-3.5 py-3", className)}>
      <div className="shadow-sm flex w-full items-center gap-2 rounded-md border border-subtle bg-layer-2 px-3 py-2">
        <span className="text-12 font-medium text-primary">{selectedEntityIds.length} selected</span>

        <select
          aria-label="Set state for the selection"
          className={controlClass}
          value=""
          disabled={busy}
          onChange={(event) => event.target.value && void apply({ state_id: event.target.value })}
        >
          <option value="">State…</option>
          {projectStates?.map((state) => (
            <option key={state.id} value={state.id}>
              {state.name}
            </option>
          ))}
        </select>

        <select
          aria-label="Set priority for the selection"
          className={controlClass}
          value=""
          disabled={busy}
          onChange={(event) => event.target.value && void apply({ priority: event.target.value })}
        >
          <option value="">Priority…</option>
          {PRIORITIES.map((priority) => (
            <option key={priority} value={priority}>
              {priority}
            </option>
          ))}
        </select>

        <button
          type="button"
          aria-label="Clear selection"
          className="ml-auto text-tertiary hover:text-primary"
          onClick={selectionHelpers.handleClearSelection}
        >
          <X className="size-4" />
        </button>
      </div>
    </div>
  );
});
