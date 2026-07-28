/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { useState } from "react";
import { AlertTriangle, CheckCircle2, Link2, Pencil, PlayCircle, Plus, ShieldAlert, Trash2 } from "lucide-react";
import { observer } from "mobx-react";
import { useParams } from "react-router";
import { useTranslation } from "@plane/i18n";
import type { TReleaseEvidence } from "@plane/types";
import { useTesting } from "@/hooks/store/use-testing";

export const TestingOverviewView = observer(function TestingOverviewView() {
  const { t } = useTranslation();
  const { workspaceSlug, projectId } = useParams();
  const { overview, requirementCoverage, upsertReleaseEvidence, deleteReleaseEvidence } = useTesting();
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [kind, setKind] = useState<TReleaseEvidence["kind"]>("slo");
  const [key, setKey] = useState("");
  const [name, setName] = useState("");
  const [status, setStatus] = useState<TReleaseEvidence["status"]>("pending");
  const [detail, setDetail] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [savingEvidence, setSavingEvidence] = useState(false);
  const [evidenceError, setEvidenceError] = useState("");
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
  const fieldClass =
    "h-9 rounded border border-subtle bg-surface-1 px-2 text-12 text-primary outline-none focus:border-accent-strong";

  const resetEvidenceForm = () => {
    setEditingKey(null);
    setKind("slo");
    setKey("");
    setName("");
    setStatus("pending");
    setDetail("");
    setSourceUrl("");
    setEvidenceError("");
  };

  const editEvidence = (item: TReleaseEvidence) => {
    setEditingKey(item.key);
    setKind(item.kind);
    setKey(item.key);
    setName(item.name);
    setStatus(item.status);
    setDetail(item.detail);
    setSourceUrl(item.source_url);
    setEvidenceError("");
  };

  const saveEvidence = async () => {
    const slug = workspaceSlug?.toString();
    const project = projectId?.toString();
    if (!slug || !project || !key.trim() || !name.trim()) return;
    setSavingEvidence(true);
    setEvidenceError("");
    try {
      await upsertReleaseEvidence(slug, project, {
        kind,
        key: key.trim(),
        name: name.trim(),
        status,
        detail: detail.trim(),
        source_url: sourceUrl.trim(),
      });
      resetEvidenceForm();
    } catch (error) {
      setEvidenceError(
        error && typeof error === "object" && "error" in error ? String(error.error) : "Unable to save evidence."
      );
    } finally {
      setSavingEvidence(false);
    }
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
        {cards.map(({ label, value, detail: cardDetail, icon: Icon }) => (
          <div key={label} className="rounded-lg border border-subtle bg-surface-1 p-4">
            <div className="flex items-center gap-2 text-12 text-secondary">
              <Icon className="size-4" /> {label}
            </div>
            <p className="mt-3 text-24 font-semibold text-primary">{value}</p>
            <p className="mt-1 text-11 text-tertiary">{cardDetail}</p>
          </div>
        ))}
      </div>
      {overview.latest_run && (
        <section className="rounded-lg border border-subtle bg-surface-1 p-4">
          <h2 className="text-14 font-semibold text-primary">Latest run · {overview.latest_run.name}</h2>
          <div className="mt-4 grid grid-cols-5 gap-2">
            {(["passed", "failed", "blocked", "skipped", "open"] as const).map((resultStatus) => (
              <div key={resultStatus} className="rounded bg-layer-1 p-3">
                <p className="text-18 font-semibold text-primary">{overview.latest_run?.[resultStatus]}</p>
                <p className="text-11 text-secondary capitalize">{resultStatus}</p>
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
                  .map(([configurationKey, value]) => `${configurationKey}: ${String(value)}`)
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
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-14 font-semibold text-primary">{t("testing.overview.evidence")}</h2>
          {editingKey && (
            <button
              type="button"
              className="text-11 font-medium text-secondary hover:text-primary"
              onClick={resetEvidenceForm}
            >
              Cancel editing
            </button>
          )}
        </div>
        {/* Availability is last month's measurement and a sign-off is a decision;
            neither can be executed before shipping, so they are recorded rather
            than tested, and the gate reads them alongside the run results. */}
        <p className="mt-1 text-12 text-secondary">{t("testing.overview.evidence_hint")}</p>
        {overview.release_evidence.length ? (
          <ul className="mt-3 space-y-2">
            {overview.release_evidence.map((item) => (
              <li key={item.id} className="flex flex-wrap items-center gap-3 rounded border border-subtle p-2 text-12">
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
                <span className="ml-auto flex items-center gap-1">
                  <button
                    type="button"
                    className="rounded p-1.5 text-tertiary hover:bg-layer-2 hover:text-primary"
                    aria-label={`Edit ${item.name}`}
                    onClick={() => editEvidence(item)}
                  >
                    <Pencil className="size-3.5" />
                  </button>
                  <button
                    type="button"
                    className="rounded p-1.5 text-tertiary hover:bg-danger-subtle hover:text-danger-primary"
                    aria-label={`Delete ${item.name}`}
                    onClick={() => {
                      const slug = workspaceSlug?.toString();
                      const project = projectId?.toString();
                      if (!slug || !project || !window.confirm(`Delete release evidence ${item.name}?`)) return;
                      void deleteReleaseEvidence(slug, project, item.key).catch(() =>
                        setEvidenceError("Unable to delete evidence.")
                      );
                    }}
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-12 text-tertiary">{t("testing.overview.evidence_empty")}</p>
        )}
        <div className="mt-4 grid grid-cols-1 gap-2 border-t border-subtle pt-4 md:grid-cols-2 lg:grid-cols-3">
          <input
            className={fieldClass}
            value={key}
            disabled={Boolean(editingKey)}
            onChange={(event) => setKey(event.target.value)}
            placeholder="Stable key, e.g. availability-slo"
          />
          <input
            className={fieldClass}
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Evidence name"
          />
          <select
            className={fieldClass}
            value={kind}
            onChange={(event) => setKind(event.target.value as TReleaseEvidence["kind"])}
          >
            <option value="slo">SLO</option>
            <option value="scan">Scan</option>
            <option value="review">Review</option>
            <option value="other">Other</option>
          </select>
          <select
            className={fieldClass}
            value={status}
            onChange={(event) => setStatus(event.target.value as TReleaseEvidence["status"])}
          >
            <option value="passing">Passing</option>
            <option value="failing">Failing</option>
            <option value="pending">Pending</option>
          </select>
          <input
            className={fieldClass}
            value={sourceUrl}
            onChange={(event) => setSourceUrl(event.target.value)}
            placeholder="Source URL (optional)"
          />
          <input
            className={fieldClass}
            value={detail}
            onChange={(event) => setDetail(event.target.value)}
            placeholder="Decision detail"
          />
        </div>
        <div className="mt-3 flex items-center justify-between gap-3">
          <span className="text-11 text-danger-primary">{evidenceError}</span>
          <button
            type="button"
            className="inline-flex h-8 items-center gap-1.5 rounded bg-accent-primary px-3 text-12 font-medium text-on-color disabled:opacity-50"
            disabled={savingEvidence || !key.trim() || !name.trim()}
            onClick={() => void saveEvidence()}
          >
            <Plus className="size-3.5" /> {editingKey ? "Save evidence" : "Add evidence"}
          </button>
        </div>
      </section>
    </div>
  );
});
