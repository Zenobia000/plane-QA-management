/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { Check, ChevronDown, ChevronRight, X } from "lucide-react";
import { Link } from "react-router";
import { useTranslation } from "@plane/i18n";
import type { TFrontlineGroup, TFrontlineTriage, TProjectFrontline } from "@plane/types";

type Props = {
  workspaceSlug: string;
  projectId: string;
  data: TProjectFrontline | null;
  /** Only admins may retriage, which is the intake endpoint's own rule, not a new one. */
  canTriage: boolean;
  onTriage: (issueId: string, status: number) => Promise<void>;
};

/** `IntakeIssueStatus` on the server. Named here so the call sites read as decisions. */
const ACCEPTED = 1;
const REJECTED = -1;

const TRIAGE_CLASSES: Record<TFrontlineTriage, string> = {
  pending: "bg-warning-subtle text-warning-primary",
  accepted: "bg-success-subtle text-success-primary",
  declined: "bg-surface-2 text-tertiary",
};

// Spelled out rather than built from the value, so every key stays greppable and the typed
// `t()` union still checks them.
const TRIAGE_KEYS: Record<TFrontlineTriage, string> = {
  pending: "project_overview.frontline.triage.pending",
  accepted: "project_overview.frontline.triage.accepted",
  declined: "project_overview.frontline.triage.declined",
};

function GroupRow({
  group,
  workspaceSlug,
  projectId,
  canTriage,
  onTriage,
}: {
  group: TFrontlineGroup;
  workspaceSlug: string;
  projectId: string;
  canTriage: boolean;
  onTriage: (issueId: string, status: number) => Promise<void>;
}) {
  // Groups with unhandled reports open by default. What is waiting is the reason to look.
  const [open, setOpen] = useState(group.pending > 0);
  const [busy, setBusy] = useState<string | null>(null);
  const { t } = useTranslation();

  const triage = async (issueId: string, status: number) => {
    setBusy(issueId);
    try {
      await onTriage(issueId, status);
    } finally {
      setBusy(null);
    }
  };

  return (
    <li className="border-t border-subtle py-2 first:border-t-0">
      <button
        type="button"
        className="flex w-full items-center gap-2 text-left"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        {open ? (
          <ChevronDown className="size-3.5 shrink-0 text-tertiary" />
        ) : (
          <ChevronRight className="size-3.5 shrink-0 text-tertiary" />
        )}
        <span className="truncate text-12 font-medium text-primary">
          {group.label ?? t("project_overview.frontline.unattributed")}
        </span>
        <span className="text-11 text-tertiary">{group.total}</span>
        {group.pending > 0 && (
          <span className="rounded bg-warning-subtle px-1.5 py-0.5 text-10 font-medium text-warning-primary">
            {t("project_overview.frontline.pending_count", { count: group.pending })}
          </span>
        )}
        {!group.pending && group.accepted > 0 && (
          <span className="text-10 text-success-primary">{t("project_overview.frontline.all_scheduled")}</span>
        )}
      </button>

      {open && (
        <ul className="mt-1.5 space-y-1 pl-5">
          {group.items.map((item) => (
            <li key={item.id} className="flex items-center gap-2">
              <span className={`shrink-0 rounded px-1.5 py-0.5 text-10 font-medium ${TRIAGE_CLASSES[item.triage]}`}>
                {t(TRIAGE_KEYS[item.triage])}
              </span>
              <Link
                to={`/${workspaceSlug}/projects/${projectId}/issues/${item.issue_id}`}
                className="min-w-0 flex-1 truncate text-12 text-secondary hover:text-primary hover:underline"
              >
                {item.name}
              </Link>
              {/* A status change, not a form. Retriage is one decision already made in the
                  reader's head by the time they reach this row. */}
              {canTriage && item.triage === "pending" && (
                <span className="flex shrink-0 items-center gap-0.5">
                  <button
                    type="button"
                    aria-label={t("project_overview.frontline.accept")}
                    title={t("project_overview.frontline.accept")}
                    disabled={busy === item.issue_id}
                    className="rounded p-1 text-tertiary hover:bg-success-subtle hover:text-success-primary disabled:opacity-50"
                    onClick={() => void triage(item.issue_id, ACCEPTED)}
                  >
                    <Check className="size-3" />
                  </button>
                  <button
                    type="button"
                    aria-label={t("project_overview.frontline.decline")}
                    title={t("project_overview.frontline.decline")}
                    disabled={busy === item.issue_id}
                    className="rounded p-1 text-tertiary hover:bg-danger-subtle hover:text-danger-primary disabled:opacity-50"
                    onClick={() => void triage(item.issue_id, REJECTED)}
                  >
                    <X className="size-3" />
                  </button>
                </span>
              )}
            </li>
          ))}
          {/* Never truncate silently: a group showing five of twelve reads as a group of five. */}
          {group.total > group.items.length && (
            <li className="text-11 text-tertiary">
              {t("project_overview.frontline.more_in_group", { count: group.total - group.items.length })}
            </li>
          )}
        </ul>
      )}
    </li>
  );
}

/**
 * Who is unhappy, about what, and whether anyone has picked it up.
 *
 * This is the panel the whole redesign exists for: complaints arriving from the field have
 * to reach engineering, and until now Intake held them as a flat queue that answered "how
 * many" and never "whose".
 *
 * Every heading on this panel -- including its own title -- is a string the project typed
 * into settings. The client is told which property to group by and renders whatever comes
 * back, so a team that thinks in tenants or regions gets the same panel without a fork.
 *
 * Renders nothing when the project has marked no grouping property. An empty frame with a
 * "configure me" message would be a permanent piece of furniture on every project that has
 * decided it does not need this.
 */
export function FrontlinePanel({ workspaceSlug, projectId, data, canTriage, onTriage }: Props) {
  const { t } = useTranslation();

  if (!data?.dimension || !data.groups.length) return null;
  const { totals } = data;

  // The group headings below add up to more than the summary whenever a report names two
  // accounts, because it is listed under both. That is the right rendering of one bug two
  // customers reported, but on screen it is two numbers that disagree and nothing saying
  // why -- so the panel states the arithmetic instead of leaving the reader to doubt it.
  const grouped = data.groups.reduce((running, group) => running + group.total, 0);

  return (
    <section className="rounded border border-subtle p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-13 font-medium text-primary">{data.dimension.name}</h2>
        <Link
          to={`/${workspaceSlug}/projects/${projectId}/intake`}
          className="shrink-0 text-11 font-medium text-accent-primary hover:underline"
        >
          {t("project_overview.frontline.open_intake")}
        </Link>
      </div>
      <p className="mt-0.5 text-11 text-tertiary">
        {t("project_overview.frontline.summary", {
          reports: totals.reports,
          pending: totals.pending,
          accepted: totals.accepted,
          declined: totals.declined,
        })}
      </p>
      {totals.multi_attributed > 0 && (
        <p className="mt-0.5 text-11 text-tertiary">
          {t("project_overview.frontline.multi_attributed", {
            count: totals.multi_attributed,
            dimension: data.dimension.name,
            sum: grouped,
            total: totals.reports,
          })}
        </p>
      )}

      <ul className="mt-3">
        {data.groups.map((group) => (
          <GroupRow
            key={group.value ?? "__unattributed__"}
            group={group}
            workspaceSlug={workspaceSlug}
            projectId={projectId}
            canTriage={canTriage}
            onTriage={onTriage}
          />
        ))}
      </ul>
    </section>
  );
}
