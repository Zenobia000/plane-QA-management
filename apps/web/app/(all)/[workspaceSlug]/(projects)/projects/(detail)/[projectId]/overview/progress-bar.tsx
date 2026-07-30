/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TProjectProgress } from "@plane/types";

const GROUPS = [
  { key: "completed", label: "Completed", className: "bg-success-solid" },
  { key: "started", label: "Started", className: "bg-warning-solid" },
  { key: "unstarted", label: "Unstarted", className: "bg-neutral-solid" },
  { key: "backlog", label: "Backlog", className: "bg-surface-3" },
] as const;

/**
 * The completion bar, over work that is still owed.
 *
 * Cancelled items are shown in the legend but excluded from the bar, matching the
 * denominator the endpoint reports: counting cancelled work as outstanding describes a
 * project as behind on work nobody owes.
 */
export function ProgressBar({ progress }: { progress: TProjectProgress }) {
  const { state_distribution: distribution, in_scope: inScope } = progress;

  return (
    <section className="rounded border border-subtle p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-13 font-medium text-primary">Progress</h2>
        <p className="text-12 text-secondary">
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
                className={group.className}
                style={{ width: `${(count / inScope) * 100}%` }}
                title={`${group.label}: ${count}`}
              />
            );
          })}
      </div>

      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
        {GROUPS.map((group) => (
          <li key={group.key} className="flex items-center gap-1.5 text-11 text-tertiary">
            <span className={`size-2 rounded-sm ${group.className}`} />
            {group.label} {distribution[group.key]}
          </li>
        ))}
        {distribution.cancelled > 0 && (
          <li className="text-11 text-tertiary" title="Out of scope, so not counted in the bar">
            Cancelled {distribution.cancelled}
          </li>
        )}
      </ul>
    </section>
  );
}
