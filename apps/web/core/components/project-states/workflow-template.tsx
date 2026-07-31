/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import useSWR from "swr";
import { Layers } from "lucide-react";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
// services
import { ProjectStateService } from "@/services/project/project-state.service";

const projectStateService = new ProjectStateService();

type Props = {
  workspaceSlug: string;
  projectId: string;
  isEditable: boolean;
  onApplied: () => Promise<unknown>;
};

/**
 * Offers this fork's delivery workflow to a project that does not have it.
 *
 * The fifteen `SDLC_STATES` were only ever reachable through `seed_testing_demo`; a project
 * created any other way gets five, one per group, and the settings page then reads as
 * though the five groups are all there is. Nine of the missing states are `started`, which
 * is the whole point of the set -- a board that shows where work sits rather than that it
 * has started.
 *
 * Purely additive, and it says what it will add before adding it. Existing states are never
 * renamed, moved or removed, so no work item changes state.
 */
export function WorkflowTemplateBanner({ workspaceSlug, projectId, isEditable, onApplied }: Props) {
  const [applying, setApplying] = useState(false);

  const { data: plan, mutate } = useSWR(
    isEditable ? `PROJECT_STATE_TEMPLATE_${workspaceSlug}_${projectId}` : null,
    isEditable ? () => projectStateService.previewWorkflowTemplate(workspaceSlug, projectId) : null,
    { revalidateOnFocus: false }
  );

  // Nothing to offer once the project already carries the workflow.
  if (!isEditable || !plan?.missing?.length) return null;

  const apply = async () => {
    setApplying(true);
    try {
      const result = await projectStateService.applyWorkflowTemplate(workspaceSlug, projectId);
      await Promise.all([onApplied(), mutate()]);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Workflow applied",
        message: `Added ${result.missing.length ? result.missing.length : plan.missing.length} states.`,
      });
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Workflow not applied",
        message: "The states could not be added.",
      });
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="mb-4 flex items-start gap-3 rounded border border-subtle bg-surface-2 p-3">
      <Layers className="mt-0.5 size-4 shrink-0 text-tertiary" />
      <div className="min-w-0 flex-1">
        <p className="text-13 font-medium text-primary">Use the SDLC delivery workflow</p>
        <p className="mt-0.5 text-12 text-tertiary">
          Adds {plan.missing.length} states this project does not have, including the review and testing stages that
          make a board show where work sits. Nothing existing is renamed or removed.
        </p>
        <p className="mt-1 truncate text-11 text-tertiary" title={plan.missing.join(", ")}>
          {plan.missing.join(" · ")}
        </p>
      </div>
      <button
        type="button"
        className="h-8 shrink-0 rounded bg-accent-primary px-3 text-12 font-medium text-on-color disabled:opacity-50"
        disabled={applying}
        onClick={() => void apply()}
      >
        {applying ? "Applying…" : "Apply"}
      </button>
    </div>
  );
}
