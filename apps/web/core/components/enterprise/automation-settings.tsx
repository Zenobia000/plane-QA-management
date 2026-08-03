/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { EnterpriseService } from "@plane/services";
import type { TAutomation } from "@plane/types";

const fieldClass =
  "h-8 rounded border border-subtle bg-surface-1 px-2 text-12 text-primary outline-none focus:border-accent-strong";

const STATE_GROUPS = ["backlog", "unstarted", "started", "completed", "cancelled"];
const PRIORITIES = ["urgent", "high", "medium", "low", "none"];

const service = new EnterpriseService();

/**
 * Rules that act on a work item when it enters a state group.
 *
 * The form offers exactly what the engine supports and nothing more. Presenting a condition
 * builder over an engine with one trigger would promise expressiveness that does not exist,
 * and the first person to try a second condition would find out the hard way.
 */
export function AutomationSettings({ workspaceSlug, projectId }: { workspaceSlug: string; projectId: string }) {
  const [rules, setRules] = useState<TAutomation[]>([]);
  const [name, setName] = useState("");
  const [group, setGroup] = useState("completed");
  const [priority, setPriority] = useState("low");

  const load = useCallback(async () => {
    setRules(await service.listAutomations(workspaceSlug, projectId).catch(() => []));
  }, [workspaceSlug, projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="space-y-4">
      <header>
        <h2 className="text-14 font-medium text-primary">Automations</h2>
        <p className="mt-1 text-12 text-tertiary">
          When a work item enters a state group, set a field on it. Actions never trigger other rules.
        </p>
      </header>

      <ul className="divide-y divide-subtle rounded border border-subtle">
        {rules.map((rule) => (
          <li key={rule.id} className="flex items-center gap-2 px-3 py-2 text-12">
            <span className="text-primary">{rule.name}</span>
            <span className="text-tertiary">
              on {rule.trigger_state_group} → priority {rule.actions?.priority ?? "—"}
            </span>
            {!rule.is_active && <span className="text-11 text-tertiary">(off)</span>}
            <button
              type="button"
              aria-label="Remove automation"
              className="ml-auto text-tertiary hover:text-danger-primary"
              onClick={async () => {
                await service.deleteAutomation(workspaceSlug, projectId, rule.id);
                await load();
              }}
            >
              <Trash2 className="size-3.5" />
            </button>
          </li>
        ))}
        {!rules.length && <li className="px-3 py-4 text-12 text-tertiary">No automations.</li>}
      </ul>

      <div className="flex flex-wrap items-center gap-2">
        <input
          aria-label="Automation name"
          className={fieldClass}
          placeholder="Rule name"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <select
          aria-label="Trigger state group"
          className={fieldClass}
          value={group}
          onChange={(event) => setGroup(event.target.value)}
        >
          {STATE_GROUPS.map((option) => (
            <option key={option} value={option}>
              enters {option}
            </option>
          ))}
        </select>
        <select
          aria-label="Set priority"
          className={fieldClass}
          value={priority}
          onChange={(event) => setPriority(event.target.value)}
        >
          {PRIORITIES.map((option) => (
            <option key={option} value={option}>
              set priority {option}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="h-8 rounded bg-accent-primary px-3 text-12 font-medium text-inverse disabled:opacity-50"
          disabled={!name.trim()}
          onClick={async () => {
            await service.createAutomation(workspaceSlug, projectId, {
              name: name.trim(),
              trigger_state_group: group,
              actions: { priority },
            });
            setName("");
            await load();
          }}
        >
          Add rule
        </button>
      </div>
    </section>
  );
}
