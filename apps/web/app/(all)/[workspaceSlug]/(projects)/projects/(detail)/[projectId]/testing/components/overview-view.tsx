/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { AlertTriangle, CheckCircle2, Link2, PlayCircle, ShieldAlert } from "lucide-react";
import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";
import { useTesting } from "@/hooks/store/use-testing";

export const TestingOverviewView = observer(function TestingOverviewView() {
  const { t } = useTranslation();
  const { overview, requirementCoverage } = useTesting();
  if (!overview)
    return (
      <div className="flex flex-1 items-center justify-center text-13 text-secondary">
        {t("testing.loading_overview")}
      </div>
    );
  // Requirement coverage and library hygiene are different questions. The first
  // decides whether the work is verified; the second only says how tidy the case
  // library is. Showing the second under the first one's name is what made a
  // fully-linked library read as fully-covered delivery.
  const cards = [
    {
      label: t("testing.overview.requirement_coverage"),
      value: `${overview.requirements.coverage_percent}%`,
      detail: t("testing.overview.requirement_coverage_detail", {
        covered: overview.requirements.covered,
        total: overview.requirements.total,
      }),
      icon: Link2,
    },
    {
      label: t("testing.overview.unverified"),
      value: overview.requirements.uncovered,
      detail: t("testing.overview.unverified_detail"),
      icon: ShieldAlert,
    },
    {
      label: t("testing.overview.active_runs"),
      value: overview.runs.active,
      detail: t("testing.overview.active_runs_detail", { total: overview.runs.total }),
      icon: PlayCircle,
    },
    {
      label: t("testing.overview.open_defects"),
      value: overview.open_defects,
      detail: t("testing.overview.open_defects_detail"),
      icon: AlertTriangle,
    },
  ];
  const evidenceStyle: Record<string, string> = {
    passing: "bg-success-subtle text-success-primary",
    failing: "bg-danger-subtle text-danger-primary",
    pending: "bg-layer-2 text-secondary",
  };

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-20 font-semibold text-primary">{t("testing.overview.heading")}</h1>
        <p className="mt-1 text-13 text-secondary">
          Requirement coverage, latest execution evidence, and an explainable release gate.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {cards.map(({ label, value, detail, icon: Icon }) => (
          <div key={label} className="rounded-lg border border-subtle bg-surface-1 p-4">
            <div className="flex items-center gap-2 text-12 text-secondary">
              <Icon className="size-4" /> {label}
            </div>
            <p className="mt-3 text-24 font-semibold text-primary">{value}</p>
            <p className="mt-1 text-11 text-tertiary">{detail}</p>
          </div>
        ))}
      </div>
      {overview.latest_run && (
        <section className="rounded-lg border border-subtle bg-surface-1 p-4">
          <h2 className="text-14 font-semibold text-primary">Latest run · {overview.latest_run.name}</h2>
          <div className="mt-4 grid grid-cols-5 gap-2">
            {(["passed", "failed", "blocked", "skipped", "open"] as const).map((status) => (
              <div key={status} className="rounded bg-layer-1 p-3">
                <p className="text-18 font-semibold text-primary">{overview.latest_run?.[status]}</p>
                <p className="text-11 text-secondary capitalize">{status}</p>
              </div>
            ))}
          </div>
        </section>
      )}
      {overview.scorecards.length > 0 && (
        <section className="overflow-hidden rounded-lg border border-subtle bg-surface-1">
          <div className="border-b border-subtle p-4">
            <h2 className="text-14 font-semibold text-primary">Run scorecards</h2>
            <p className="mt-1 text-11 text-secondary">
              Compare builds and configurations using latest status per pinned case.
            </p>
          </div>
          {overview.scorecards.map((run) => (
            <div
              key={run.id}
              className="grid grid-cols-[1fr_7rem_repeat(4,4rem)] gap-3 border-b border-subtle px-4 py-3 text-12 last:border-0"
            >
              <span>
                <span className="block font-medium text-primary">{run.name}</span>
                <span className="text-tertiary">{run.build || "No build"}</span>
              </span>
              <span className="truncate text-secondary">
                {Object.entries(run.configuration)
                  .map(([key, value]) => `${key}: ${String(value)}`)
                  .join(", ") || "Default"}
              </span>
              <span className="text-success-primary">{run.passed} pass</span>
              <span className="text-danger-primary">{run.failed} fail</span>
              <span className="text-warning-primary">{run.blocked} block</span>
              <span className="text-secondary">{run.open} open</span>
            </div>
          ))}
        </section>
      )}
      {requirementCoverage && (
        <section className="overflow-hidden rounded-lg border border-subtle bg-surface-1">
          <div className="border-b border-subtle p-4">
            <h2 className="text-14 font-semibold text-primary">Requirement coverage</h2>
            <p className="mt-1 text-11 text-secondary">
              {requirementCoverage.covered} covered · {requirementCoverage.uncovered} uncovered work items
            </p>
          </div>
          {requirementCoverage.work_items.map((item) => (
            <div
              key={item.work_item_id}
              className="grid grid-cols-[5rem_1fr_7rem_7rem] gap-3 border-b border-subtle px-4 py-3 text-12 last:border-0"
            >
              <span className="text-tertiary">#{item.sequence_id}</span>
              <span className="text-primary">{item.name}</span>
              <span className={item.covered ? "text-success-primary" : "text-danger-primary"}>
                {item.covered ? `${item.test_case_ids.length} case(s)` : "Uncovered"}
              </span>
              <span className="text-secondary capitalize">{item.latest_status ?? "No evidence"}</span>
            </div>
          ))}
          {!requirementCoverage.work_items.length && (
            <p className="p-5 text-center text-12 text-secondary">No work items to evaluate.</p>
          )}
        </section>
      )}
      <section
        className={`rounded-lg border p-4 ${overview.release_gate.ready ? "border-success-subtle bg-success-subtle" : "border-danger-subtle bg-danger-subtle"}`}
      >
        <div className="flex items-center gap-2">
          <CheckCircle2 className="size-5" />
          <h2 className="text-14 font-semibold text-primary">
            {t("testing.overview.release_gate")}:{" "}
            {overview.release_gate.ready ? t("testing.overview.ready") : t("testing.overview.not_ready")}
          </h2>
        </div>
        {overview.release_gate.blockers.length ? (
          <ul className="mt-3 list-disc space-y-1 pl-5 text-12 text-secondary">
            {overview.release_gate.blockers.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : null}
      </section>
      <section className="rounded-lg border border-subtle bg-surface-1 p-4">
        <h2 className="text-14 font-semibold text-primary">{t("testing.overview.evidence")}</h2>
        {/* Availability is last month's measurement and a sign-off is a decision;
            neither can be executed before shipping, so they are recorded rather
            than tested, and the gate reads them alongside the run results. */}
        <p className="mt-1 text-12 text-secondary">{t("testing.overview.evidence_hint")}</p>
        {overview.release_evidence.length ? (
          <ul className="mt-3 space-y-2">
            {overview.release_evidence.map((item) => (
              <li key={item.id} className="flex flex-wrap items-center gap-3 text-12">
                <span
                  className={`w-20 shrink-0 rounded px-1.5 py-0.5 text-center text-10 font-medium ${evidenceStyle[item.status]}`}
                >
                  {t(`testing.overview.evidence_status.${item.status}`)}
                </span>
                <span className="text-11 text-tertiary">{t(`testing.overview.kind.${item.kind}`)}</span>
                {item.source_url ? (
                  <a href={item.source_url} className="font-medium text-accent-primary hover:underline">
                    {item.name}
                  </a>
                ) : (
                  <span className="font-medium text-primary">{item.name}</span>
                )}
                {item.detail && <span className="text-secondary">{item.detail}</span>}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-12 text-tertiary">{t("testing.overview.evidence_empty")}</p>
        )}
      </section>
    </div>
  );
});
