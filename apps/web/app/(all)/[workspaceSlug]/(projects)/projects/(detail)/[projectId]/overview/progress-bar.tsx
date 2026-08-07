/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { STATE_GROUPS } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import type { TProjectProgress } from "@plane/types";

/**
 * Coloured from STATE_GROUPS rather than from Tailwind classes.
 *
 * The first version named `bg-success-solid`, `bg-warning-solid`, `bg-neutral-solid` and
 * `bg-surface-3`. None of those tokens exists -- the design system defines
 * `bg-success-primary`, `bg-warning-primary` and surfaces 1 and 2 -- so every segment
 * rendered transparent and the bar read as empty at 32% complete. Taking the colours from
 * the constant the rest of the app already uses for state groups means the bar cannot
 * drift from a board or a chart showing the same thing, and there is no class name to
 * invent.
 */
const GROUPS = [
  { key: "completed", label: STATE_GROUPS.completed.label, color: STATE_GROUPS.completed.color },
  { key: "started", label: STATE_GROUPS.started.label, color: STATE_GROUPS.started.color },
  { key: "unstarted", label: STATE_GROUPS.unstarted.label, color: STATE_GROUPS.unstarted.color },
  { key: "backlog", label: STATE_GROUPS.backlog.label, color: STATE_GROUPS.backlog.color },
] as const;

/**
 * The completion bar, over work that is still owed.
 *
 * Cancelled items are shown in the legend but excluded from the bar, matching the
 * denominator the endpoint reports: counting cancelled work as outstanding describes a
 * project as behind on work nobody owes.
 */
export function ProgressBar({ progress }: { progress: TProjectProgress }) {
  const { t } = useTranslation();
  const { state_distribution: distribution, in_scope: inScope } = progress;

  return (
    <section className="rounded border border-subtle p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-13 font-medium text-primary">{t("project_overview.progress.title")}</h2>
        {/* Says what it counts, because the readiness panel above renders its own "X / Y"
            over a narrower population -- scheduled requirements that need an acceptance
            contract, not every work item. Two ratios in the same column with different
            denominators and no definitions read as one number contradicting itself. */}
        <p className="text-12 text-secondary" title={t("project_overview.progress.counts")}>
          {progress.completed} / {inScope} done
          <span className="ml-2 font-medium text-primary">{progress.completion_percentage}%</span>
        </p>
      </div>

      <div className="mt-3 flex h-2 overflow-hidden rounded bg-surface-2">
        {inScope > 0 &&
          GROUPS.map((group) => {
            const count = distribution[group.key];
            if (!count) return null;
            return (
              <div
                key={group.key}
                style={{ width: `${(count / inScope) * 100}%`, backgroundColor: group.color }}
                title={`${group.label}: ${count}`}
              />
            );
          })}
      </div>

      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
        {GROUPS.map((group) => (
          <li key={group.key} className="flex items-center gap-1.5 text-11 text-tertiary">
            <span className="size-2 rounded-sm" style={{ backgroundColor: group.color }} />
            {group.label} {distribution[group.key]}
          </li>
        ))}
        {distribution.cancelled > 0 && (
          <li className="text-11 text-tertiary" title={t("project_overview.progress.out_of_scope")}>
            Cancelled {distribution.cancelled}
          </li>
        )}
      </ul>
    </section>
  );
}
