/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { AlertTriangle } from "lucide-react";
import { Link } from "react-router";
import { useTranslation } from "@plane/i18n";
import type { TProjectAttention } from "@plane/types";

type Props = {
  workspaceSlug: string;
  projectId: string;
  data: TProjectAttention | null;
};

/**
 * The few work items that will go wrong first.
 *
 * The overview's other panels report aggregates -- how much is done, how many complaints
 * arrived. None of them names a thing to do. This one does, and it is deliberately short:
 * a list of forty is a work-item view with worse filtering, and nobody reads it.
 *
 * Ordering is the server's and is not re-sorted here. Overdue leads because a missed date
 * is a fact and a priority is an opinion.
 *
 * Renders nothing when nothing is overdue or urgent. A panel that says "all clear" every
 * day trains people to skip the region of the screen where the alarm will appear.
 */
export function AttentionPanel({ workspaceSlug, projectId, data }: Props) {
  const { t } = useTranslation();

  if (!data?.items.length) return null;
  const hidden = data.total_overdue + data.total_urgent - data.items.length;

  return (
    <section className="rounded border border-subtle p-4">
      <div className="flex items-center gap-2">
        <AlertTriangle className="size-4 shrink-0 text-warning-primary" />
        <h2 className="text-13 font-medium text-primary">{t("project_overview.attention.title")}</h2>
        <span className="text-11 text-tertiary">
          {t("project_overview.attention.summary", {
            overdue: data.total_overdue,
            urgent: data.total_urgent,
          })}
        </span>
      </div>

      <ul className="mt-3 space-y-1.5">
        {data.items.map((item) => (
          <li key={item.id} className="flex items-center gap-2">
            <span
              className={`shrink-0 rounded px-1.5 py-0.5 text-10 font-medium ${
                item.days_overdue > 0
                  ? "bg-danger-subtle text-danger-primary"
                  : "bg-warning-subtle text-warning-primary"
              }`}
            >
              {item.days_overdue > 0
                ? t("project_overview.attention.overdue_by", { count: item.days_overdue })
                : t("project_overview.attention.urgent")}
            </span>
            <Link
              to={`/${workspaceSlug}/projects/${projectId}/issues/${item.id}`}
              className="min-w-0 flex-1 truncate text-12 text-secondary hover:text-primary hover:underline"
            >
              {item.name}
            </Link>
            <span className="shrink-0 text-11 text-tertiary">
              {item.assignees.length
                ? item.assignees.map((assignee) => assignee.display_name).join(", ")
                : t("project_overview.attention.unassigned")}
            </span>
          </li>
        ))}
      </ul>

      {/* The cap is visible rather than implied, so five never reads as all there is. */}
      {hidden > 0 && (
        <p className="mt-2 text-11 text-tertiary">{t("project_overview.attention.more", { count: hidden })}</p>
      )}
    </section>
  );
}
