/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import useSWR from "swr";
import { AlertTriangle, CheckCircle2, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useTranslation } from "@plane/i18n";
import { TestingService } from "@plane/services";

const testingService = new TestingService();

type Props = {
  workspaceSlug: string;
  projectId: string;
};

/**
 * Whether this project can ship, and what is stopping it.
 *
 * The rest of this page reports how much work is done. That is not the question a delivery
 * decision turns on, and `testing-product-definition.md` says so directly: P4's success is
 * "knowing the state without opening the Testing tab; a shipping decision with evidence
 * behind it rather than an impression". Overview is the surface that promise lands on, and
 * until now it said nothing about coverage, defects or the gate.
 *
 * Every line here is computed by `release_gate` on the server -- uncovered requirements,
 * failed and blocked cases in the latest run, open defects, unrecorded evidence. None of it
 * is a threshold invented in the client, which is the trap a "looks behind schedule" banner
 * would fall into: a number nobody agreed on, drifting away from what the gate decides.
 *
 * Renders nothing when the project has no testing data. A project not using the testing
 * half should not be told it is unready.
 */
export function ReadinessPanel({ workspaceSlug, projectId }: Props) {
  const { t } = useTranslation();

  const { data } = useSWR(
    workspaceSlug && projectId ? `TESTING_OVERVIEW_${workspaceSlug}_${projectId}` : null,
    workspaceSlug && projectId ? () => testingService.getOverview(workspaceSlug, projectId) : null,
    { revalidateOnFocus: false, shouldRetryOnError: false }
  );

  if (!data) return null;
  const { release_gate: gate, requirements, latest_run: latestRun, open_defects: openDefects } = data;
  // Nothing scheduled and nothing run: the project does not use this half of the product.
  if (!requirements.total && !data.runs.total) return null;

  const ready = gate?.ready ?? false;
  const blockers = gate?.blockers ?? [];
  const testingHref = `/${workspaceSlug}/projects/${projectId}/testing/overview`;

  // Every case the run carries, not just the ones that reached a verdict. The old
  // denominator was `passed + failed + blocked`, which drops `open` and `skipped` -- so a
  // run of twenty cases with nine still unexecuted reported "8/11" and read as nearly
  // finished. The gate above already names those nine in a blocker, which left the panel
  // contradicting itself: a sentence counting cases the statistic beside it pretended were
  // not in the run.
  const runTotal = latestRun
    ? latestRun.passed + latestRun.failed + latestRun.blocked + latestRun.open + latestRun.skipped
    : 0;
  // Spelled out beside the ratio rather than left to the tooltip. "8/20" invites the reader
  // to assume twelve failures; the reason for the gap is the point.
  const runCaveats = latestRun
    ? [
        // Same wording the gate's own blocker uses, so the two cannot be read as counting
        // different things.
        latestRun.open ? t("project_overview.readiness.unexecuted", { count: latestRun.open }) : null,
        latestRun.skipped ? t("project_overview.readiness.skipped", { count: latestRun.skipped }) : null,
      ].filter(Boolean)
    : [];

  return (
    <section
      className={`rounded border p-4 ${ready ? "border-success-subtle bg-success-subtle" : "border-danger-subtle bg-danger-subtle"}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          {ready ? (
            <CheckCircle2 className="size-4 shrink-0 text-success-primary" />
          ) : (
            <AlertTriangle className="size-4 shrink-0 text-danger-primary" />
          )}
          <h2 className={`text-13 font-medium ${ready ? "text-success-primary" : "text-danger-primary"}`}>
            {ready ? t("project_overview.readiness.ready") : t("project_overview.readiness.not_ready")}
          </h2>
        </div>
        <Link
          href={testingHref}
          className="flex shrink-0 items-center gap-0.5 text-12 font-medium text-accent-primary hover:underline"
        >
          {t("project_overview.readiness.open_testing")}
          <ChevronRight className="size-3.5" />
        </Link>
      </div>

      {/* The blockers are server-computed sentences, so they arrive in English. Translating
          them would mean the gate speaking two languages that could disagree. */}
      {!!blockers.length && (
        <ul className="mt-2 space-y-1">
          {blockers.map((blocker) => (
            <li key={blocker} className="text-12 text-secondary">
              · {blocker}
            </li>
          ))}
        </ul>
      )}

      {/* Each ratio carries what it counts. This panel and the progress bar below it both
          render "X / Y" and count different populations -- requirements that are scheduled
          and need a contract here, every live work item there -- so without the definition
          the two denominators read as one number that disagrees with itself. */}
      <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 border-t border-subtle pt-3">
        <div className="flex items-baseline gap-1.5" title={t("project_overview.readiness.coverage_of")}>
          <dt className="text-11 text-tertiary">{t("project_overview.readiness.coverage")}</dt>
          <dd className="text-12 text-primary">
            {requirements.covered}/{requirements.total}
          </dd>
        </div>
        {latestRun && (
          <div className="flex items-baseline gap-1.5" title={t("project_overview.readiness.latest_run_of")}>
            <dt className="text-11 text-tertiary">{t("project_overview.readiness.latest_run")}</dt>
            <dd className="text-12 text-primary">
              {latestRun.passed}/{runTotal}
            </dd>
            {!!runCaveats.length && <dd className="text-11 text-tertiary">({runCaveats.join(" · ")})</dd>}
          </div>
        )}
        <div className="flex items-baseline gap-1.5" title={t("project_overview.readiness.open_defects_of")}>
          <dt className="text-11 text-tertiary">{t("project_overview.readiness.open_defects")}</dt>
          <dd className="text-12 text-primary">{openDefects}</dd>
        </div>
      </dl>
    </section>
  );
}
