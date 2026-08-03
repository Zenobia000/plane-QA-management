/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useState } from "react";
import { observer } from "mobx-react";
import { ArrowRight, Trash2 } from "lucide-react";
import { EnterpriseService } from "@plane/services";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import type { TStateTransition } from "@plane/types";
import { useProjectState } from "@/hooks/store/use-project-state";

const service = new EnterpriseService();

const fieldClass =
  "h-8 rounded border border-subtle bg-surface-1 px-2 text-12 text-primary outline-none focus:border-accent-strong disabled:opacity-50";

type Props = {
  workspaceSlug: string;
  projectId: string;
};

/**
 * The project's workflow, as the allow-list of edges it is.
 *
 * The empty state says what "no rules" means rather than showing a blank table, because the
 * rule that surprises people is that a state with no outgoing edge is unconstrained -- adding
 * one edge constrains that state and nothing else.
 */
export const WorkflowSettings = observer(function WorkflowSettings({ workspaceSlug, projectId }: Props) {
  const { getProjectStates } = useProjectState();
  const [transitions, setTransitions] = useState<TStateTransition[]>([]);
  const [fromState, setFromState] = useState("");
  const [toState, setToState] = useState("");
  const [requiresApproval, setRequiresApproval] = useState(false);
  const [busy, setBusy] = useState(false);

  const states = getProjectStates(projectId) ?? [];
  const nameOf = (id: string) => states.find((state) => state.id === id)?.name ?? id;

  const load = useCallback(async () => {
    try {
      setTransitions(await service.listTransitions(workspaceSlug, projectId));
    } catch {
      setTransitions([]);
    }
  }, [workspaceSlug, projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  const add = async () => {
    if (!fromState || !toState || fromState === toState) return;
    setBusy(true);
    try {
      await service.createTransition(workspaceSlug, projectId, {
        from_state: fromState,
        to_state: toState,
        requires_approval: requiresApproval,
      });
      setFromState("");
      setToState("");
      setRequiresApproval(false);
      await load();
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: "Could not add the transition." });
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    await service.deleteTransition(workspaceSlug, projectId, id);
    await load();
  };

  const constrained = new Set(transitions.map((transition) => transition.from_state));

  return (
    <section className="space-y-4">
      <header>
        <h2 className="text-14 font-medium text-primary">Workflow</h2>
        <p className="mt-1 text-12 text-tertiary">
          A state with no transition out of it allows every move. Adding one constrains that state and nothing else, so
          a workflow can be adopted a state at a time.
        </p>
      </header>

      <ul className="divide-y divide-subtle rounded border border-subtle">
        {transitions.map((transition) => (
          <li key={transition.id} className="flex items-center gap-2 px-3 py-2 text-12">
            <span className="text-primary">{nameOf(transition.from_state)}</span>
            <ArrowRight className="size-3.5 text-tertiary" />
            <span className="text-primary">{nameOf(transition.to_state)}</span>
            {transition.requires_approval && (
              <span
                className="rounded bg-warning-subtle px-1.5 py-0.5 text-10 font-medium text-warning-primary"
                title={
                  transition.approvers.length
                    ? `${transition.approvers.length} approver(s)`
                    : "No approvers configured — this move is refused for everyone"
                }
              >
                {transition.approvers.length ? "Needs approval" : "Needs approval (none set)"}
              </span>
            )}
            <button
              type="button"
              aria-label="Remove transition"
              className="ml-auto text-tertiary hover:text-danger-primary"
              onClick={() => void remove(transition.id)}
            >
              <Trash2 className="size-3.5" />
            </button>
          </li>
        ))}
        {!transitions.length && (
          <li className="px-3 py-4 text-12 text-tertiary">No rules. Every state change in this project is allowed.</li>
        )}
      </ul>

      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label="From state"
          className={fieldClass}
          value={fromState}
          onChange={(event) => setFromState(event.target.value)}
        >
          <option value="">From…</option>
          {states.map((state) => (
            <option key={state.id} value={state.id}>
              {state.name}
              {constrained.has(state.id) ? " (constrained)" : ""}
            </option>
          ))}
        </select>
        <ArrowRight className="size-3.5 text-tertiary" />
        <select
          aria-label="To state"
          className={fieldClass}
          value={toState}
          onChange={(event) => setToState(event.target.value)}
        >
          <option value="">To…</option>
          {states
            .filter((state) => state.id !== fromState)
            .map((state) => (
              <option key={state.id} value={state.id}>
                {state.name}
              </option>
            ))}
        </select>
        <label className="flex items-center gap-1.5 text-12 text-secondary">
          <input
            type="checkbox"
            checked={requiresApproval}
            onChange={(event) => setRequiresApproval(event.target.checked)}
          />
          Requires approval
        </label>
        <button
          type="button"
          className="h-8 rounded bg-accent-primary px-3 text-12 font-medium text-inverse disabled:opacity-50"
          disabled={busy || !fromState || !toState}
          onClick={() => void add()}
        >
          Add transition
        </button>
      </div>
    </section>
  );
});
