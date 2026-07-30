/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useState } from "react";
import { observer } from "mobx-react";
import { EnterpriseService } from "@plane/services";
import type { TInitiative, TInitiativeProgress } from "@plane/types";
import { useProject } from "@/hooks/store/use-project";

const service = new EnterpriseService();

const fieldClass =
  "h-8 rounded border border-subtle bg-surface-1 px-2 text-12 text-primary outline-none focus:border-accent-strong";

/**
 * Initiatives, with how far along each one is across every project it covers.
 *
 * The percentage uses the project overview's denominator -- cancelled work is out of scope
 * rather than outstanding -- because two levels reporting different figures for the same work
 * is the one way this rollup goes wrong that anybody notices.
 */
export const InitiativeList = observer(function InitiativeList({ workspaceSlug }: { workspaceSlug: string }) {
  const { joinedProjectIds, getProjectById } = useProject();
  const [initiatives, setInitiatives] = useState<TInitiative[]>([]);
  const [progress, setProgress] = useState<Record<string, TInitiativeProgress>>({});
  const [name, setName] = useState("");

  const load = useCallback(async () => {
    const list = await service.listInitiatives(workspaceSlug).catch(() => []);
    setInitiatives(list);
    const answers = await Promise.all(
      list.map((initiative) =>
        service
          .initiativeProgress(workspaceSlug, initiative.id)
          .then((data) => [initiative.id, data] as const)
          .catch(() => null)
      )
    );
    setProgress(Object.fromEntries(answers.filter(Boolean) as [string, TInitiativeProgress][]));
  }, [workspaceSlug]);

  useEffect(() => {
    void load();
  }, [load]);

  const toggleProject = async (initiative: TInitiative, projectId: string) => {
    const next = initiative.project_ids.includes(projectId)
      ? initiative.project_ids.filter((id) => id !== projectId)
      : [...initiative.project_ids, projectId];
    // The endpoint replaces the set, so the whole next state is sent rather than a delta.
    await service.setInitiativeProjects(workspaceSlug, initiative.id, next);
    await load();
  };

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-center gap-2">
        <h2 className="mr-auto text-14 font-medium text-primary">Initiatives</h2>
        <input
          aria-label="New initiative name"
          className={fieldClass}
          placeholder="New initiative"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <button
          type="button"
          className="bg-accent-solid h-8 rounded px-3 text-12 font-medium text-inverse disabled:opacity-50"
          disabled={!name.trim()}
          onClick={async () => {
            await service.createInitiative(workspaceSlug, { name: name.trim() });
            setName("");
            await load();
          }}
        >
          Create
        </button>
      </header>

      <ul className="space-y-3">
        {initiatives.map((initiative) => {
          const stats = progress[initiative.id];
          return (
            <li key={initiative.id} className="rounded border border-subtle p-3">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-13 font-medium text-primary">{initiative.name}</span>
                <span className="text-11 text-tertiary">
                  {stats ? `${stats.completed}/${stats.in_scope} · ${stats.completion_percentage}%` : "…"}
                </span>
              </div>
              {stats && (
                <div className="mt-1.5 h-1.5 overflow-hidden rounded bg-surface-2">
                  <div className="bg-success-solid h-full" style={{ width: `${stats.completion_percentage}%` }} />
                </div>
              )}
              <div className="mt-2 flex flex-wrap gap-1.5">
                {(joinedProjectIds ?? []).map((projectId) => {
                  const included = initiative.project_ids.includes(projectId);
                  return (
                    <button
                      key={projectId}
                      type="button"
                      aria-pressed={included}
                      className={`rounded px-1.5 py-0.5 text-11 ${
                        included ? "bg-accent-subtle text-accent-primary" : "bg-surface-2 text-tertiary"
                      }`}
                      onClick={() => void toggleProject(initiative, projectId)}
                    >
                      {getProjectById(projectId)?.name ?? projectId}
                    </button>
                  );
                })}
              </div>
            </li>
          );
        })}
        {!initiatives.length && <li className="text-12 text-tertiary">No initiatives yet.</li>}
      </ul>
    </section>
  );
});
