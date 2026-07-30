/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useState } from "react";
import { EnterpriseService } from "@plane/services";
import type { TDashboard, TDashboardWidget, TDashboardWidgetData } from "@plane/types";

const service = new EnterpriseService();

const fieldClass =
  "h-8 rounded border border-subtle bg-surface-1 px-2 text-12 text-primary outline-none focus:border-accent-strong";

const GROUPINGS: TDashboardWidget["group_by"][] = ["state_group", "priority", "assignee", "project"];

/** A widget's answer, drawn as proportional bars. */
function WidgetBody({ data }: { data: TDashboardWidgetData }) {
  if (!data.total) return <p className="text-12 text-tertiary">Nothing to count yet.</p>;
  if (data.chart === "number") return <p className="text-24 font-semibold text-primary">{data.total}</p>;

  return (
    <ul className="space-y-1.5">
      {data.series.map((row) => (
        <li key={row.key}>
          <div className="flex items-baseline justify-between gap-2 text-11">
            <span className="truncate text-secondary">{row.label}</span>
            <span className="shrink-0 text-tertiary">{row.count}</span>
          </div>
          <div className="mt-0.5 h-1.5 overflow-hidden rounded bg-surface-2">
            <div className="bg-accent-solid h-full" style={{ width: `${(row.count / data.total) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

/**
 * One dashboard and its widgets.
 *
 * Each widget's data is fetched on render rather than cached: a widget stores a question,
 * and a stored answer is wrong between refreshes.
 */
export function DashboardView({ workspaceSlug }: { workspaceSlug: string }) {
  const [dashboards, setDashboards] = useState<TDashboard[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [widgets, setWidgets] = useState<TDashboardWidget[]>([]);
  const [data, setData] = useState<Record<string, TDashboardWidgetData>>({});
  const [newName, setNewName] = useState("");
  const [widgetName, setWidgetName] = useState("");
  const [grouping, setGrouping] = useState<TDashboardWidget["group_by"]>("state_group");

  const loadDashboards = useCallback(async () => {
    const list = await service.listDashboards(workspaceSlug).catch(() => []);
    setDashboards(list);
    setActiveId((current) => current ?? list[0]?.id ?? null);
  }, [workspaceSlug]);

  const loadWidgets = useCallback(async () => {
    if (!activeId) return setWidgets([]);
    const list = await service.listWidgets(workspaceSlug, activeId).catch(() => []);
    setWidgets(list);
    const answers = await Promise.all(
      list.map((widget) =>
        service
          .widgetData(workspaceSlug, activeId, widget.id)
          .then((answer) => [widget.id, answer] as const)
          .catch(() => null)
      )
    );
    setData(Object.fromEntries(answers.filter(Boolean) as [string, TDashboardWidgetData][]));
  }, [workspaceSlug, activeId]);

  useEffect(() => {
    void loadDashboards();
  }, [loadDashboards]);

  useEffect(() => {
    void loadWidgets();
  }, [loadWidgets]);

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-center gap-2">
        <select
          aria-label="Dashboard"
          className={fieldClass}
          value={activeId ?? ""}
          onChange={(event) => setActiveId(event.target.value || null)}
        >
          {!dashboards.length && <option value="">No dashboards yet</option>}
          {dashboards.map((dashboard) => (
            <option key={dashboard.id} value={dashboard.id}>
              {dashboard.name}
            </option>
          ))}
        </select>
        <input
          aria-label="New dashboard name"
          className={fieldClass}
          placeholder="New dashboard"
          value={newName}
          onChange={(event) => setNewName(event.target.value)}
        />
        <button
          type="button"
          className="h-8 rounded bg-surface-2 px-3 text-12 font-medium text-primary disabled:opacity-50"
          disabled={!newName.trim()}
          onClick={async () => {
            const created = await service.createDashboard(workspaceSlug, { name: newName.trim() });
            setNewName("");
            await loadDashboards();
            setActiveId(created.id);
          }}
        >
          Create
        </button>
      </header>

      {activeId && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {widgets.map((widget) => (
              <article key={widget.id} className="rounded border border-subtle p-3">
                <h3 className="mb-2 text-12 font-medium text-primary">{widget.name}</h3>
                {data[widget.id] ? (
                  <WidgetBody data={data[widget.id]} />
                ) : (
                  <p className="text-12 text-tertiary">Loading…</p>
                )}
              </article>
            ))}
            {!widgets.length && <p className="text-12 text-tertiary">No widgets yet.</p>}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <input
              aria-label="Widget name"
              className={fieldClass}
              placeholder="Widget name"
              value={widgetName}
              onChange={(event) => setWidgetName(event.target.value)}
            />
            <select
              aria-label="Group by"
              className={fieldClass}
              value={grouping}
              onChange={(event) => setGrouping(event.target.value as TDashboardWidget["group_by"])}
            >
              {GROUPINGS.map((option) => (
                <option key={option} value={option}>
                  {option.replace("_", " ")}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="bg-accent-solid h-8 rounded px-3 text-12 font-medium text-inverse disabled:opacity-50"
              disabled={!widgetName.trim()}
              onClick={async () => {
                await service.createWidget(workspaceSlug, activeId, {
                  name: widgetName.trim(),
                  group_by: grouping,
                  chart: "bar",
                });
                setWidgetName("");
                await loadWidgets();
              }}
            >
              Add widget
            </button>
          </div>
        </>
      )}
    </section>
  );
}
