/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { Bug, Check, CircleSlash, Lock, Paperclip, SkipForward, X } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import type { TTestResultAttachment, TTestResultInput, TTestResultStatus, TTestRun } from "@plane/types";

type Props = {
  run: TTestRun;
  /** Absent means "no case addressed yet" -- the first open one is shown. */
  selectedRunCaseId?: string;
  onSelectRunCase: (runCaseId: string, options?: { replace?: boolean }) => void;
  onBack: () => void;
  onResult: (runCaseId: string, input: TTestResultInput) => Promise<void>;
  onClose: () => Promise<void>;
  onCreateDefect: (runCaseId: string, resultId: string) => Promise<unknown>;
  onListAttachments: (runCaseId: string, resultId: string) => Promise<TTestResultAttachment[]>;
  onAttach: (runCaseId: string, resultId: string, file: File) => Promise<TTestResultAttachment>;
  onDetach: (runCaseId: string, resultId: string, assetId: string) => Promise<void>;
};

const statusStyle: Record<string, string> = {
  open: "bg-layer-2 text-secondary",
  passed: "bg-success-subtle text-success-primary",
  failed: "bg-danger-subtle text-danger-primary",
  blocked: "bg-warning-subtle text-warning-primary",
  skipped: "bg-layer-2 text-tertiary",
};

const documentText = (document: Record<string, unknown>) => {
  const value = document.text ?? document.value;
  return typeof value === "string" ? value : Object.keys(document).length ? JSON.stringify(document) : "—";
};

export function ExecutionWorkspace({
  run,
  selectedRunCaseId,
  onSelectRunCase,
  onBack,
  onResult,
  onClose,
  onCreateDefect,
  onListAttachments,
  onAttach,
  onDetach,
}: Props) {
  const { t } = useTranslation();
  const [actual, setActual] = useState("");
  const [saving, setSaving] = useState(false);
  const [creatingDefect, setCreatingDefect] = useState(false);
  const [attachments, setAttachments] = useState<TTestResultAttachment[]>([]);
  const [attaching, setAttaching] = useState(false);
  const [attachError, setAttachError] = useState<string | null>(null);
  const selected = useMemo(() => {
    const addressed = selectedRunCaseId && run.run_cases.find((item) => item.id === selectedRunCaseId);
    if (addressed) return addressed;
    return run.run_cases.find((item) => item.latest_status === "open") ?? run.run_cases[0];
  }, [run.run_cases, selectedRunCaseId]);
  const latestResult = selected?.results.at(-1);
  const readyForRetest =
    !!latestResult?.defects.length &&
    latestResult.defects.every((defect) => defect.state_group === "completed" || defect.state_group === "cancelled");

  // Attachments belong to a specific result, so they reload whenever the addressed
  // result changes rather than being held per run case.
  useEffect(() => {
    let active = true;
    if (!latestResult) {
      setAttachments([]);
      return undefined;
    }
    void onListAttachments(selected!.id, latestResult.id)
      .then((items) => active && setAttachments(items))
      .catch(() => active && setAttachments([]));
    return () => {
      active = false;
    };
    // Keyed on the result identity alone: depending on the whole object would
    // reload the list on every unrelated store mutation.
    // oxlint-disable-next-line exhaustive-deps
  }, [latestResult?.id]);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
      const shortcuts: Record<string, TTestResultStatus> = { p: "passed", f: "failed", b: "blocked", s: "skipped" };
      const status = shortcuts[event.key.toLowerCase()];
      if (status && selected && run.status !== "completed") void submit(status);
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  });

  const submit = async (status: TTestResultStatus) => {
    if (!selected || run.status === "completed") return;
    setSaving(true);
    try {
      await onResult(selected.id, { status, actual_result: actual ? { text: actual } : {} });
      setActual("");
      const next = run.run_cases.find((item) => item.position > selected.position && item.latest_status === "open");
      // Advancing replaces rather than pushes: results are append-only, so a
      // history entry per recorded result would offer a Back that undoes nothing.
      if (next) onSelectRunCase(next.id, { replace: true });
    } finally {
      setSaving(false);
    }
  };

  if (!selected) return null;

  return (
    <section className="flex min-h-0 flex-1 overflow-hidden rounded-lg border border-subtle bg-surface-1">
      <aside className="w-72 shrink-0 overflow-y-auto border-r border-subtle bg-surface-2">
        <div className="border-b border-subtle p-3">
          <button type="button" onClick={onBack} className="text-12 font-medium text-accent-primary hover:underline">
            ← {t("testing.runs.all_runs")}
          </button>
          <h2 className="mt-2 text-14 font-semibold text-primary">{run.name}</h2>
          <p className="mt-1 text-11 text-secondary">
            {t("testing.runs.executed", { done: run.progress.total - run.progress.open, total: run.progress.total })}
          </p>
        </div>
        {run.run_cases.map((runCase) => (
          <button
            type="button"
            key={runCase.id}
            onClick={() => onSelectRunCase(runCase.id)}
            className={`flex w-full items-center gap-2 border-b border-subtle px-3 py-3 text-left ${
              selected.id === runCase.id ? "bg-surface-1" : "hover:bg-layer-1"
            }`}
          >
            <span
              className={`rounded px-1.5 py-0.5 text-10 font-medium capitalize ${statusStyle[runCase.latest_status]}`}
            >
              {runCase.latest_status}
            </span>
            <span className="truncate text-12 text-primary">{runCase.test_case_version.title}</span>
          </button>
        ))}
      </aside>
      <div className="flex min-w-0 flex-1 flex-col overflow-y-auto p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-11 text-tertiary">
              {t("testing.execution.case_position", {
                position: selected.position,
                version: selected.test_case_version.version,
              })}
            </div>
            <h3 className="mt-1 text-20 font-semibold text-primary">{selected.test_case_version.title}</h3>
          </div>
          {run.status === "completed" ? (
            <span className="flex items-center gap-1 rounded bg-layer-2 px-2 py-1 text-11 text-secondary">
              <Lock className="size-3" /> {t("testing.execution.closed")}
            </span>
          ) : (
            <Button variant="secondary" onClick={() => void onClose()}>
              {t("testing.execution.close_run")}
            </Button>
          )}
        </div>

        <div className="mt-6 space-y-5">
          <div>
            <h4 className="text-12 font-semibold text-secondary uppercase">{t("testing.execution.given")}</h4>
            <p className="mt-2 text-14 text-primary">{documentText(selected.test_case_version.preconditions)}</p>
          </div>
          <div>
            <h4 className="text-12 font-semibold text-secondary uppercase">{t("testing.execution.steps")}</h4>
            <ol className="mt-2 space-y-2">
              {selected.test_case_version.steps.map((step) => (
                <li
                  key={step.id}
                  className="grid grid-cols-[2rem_1fr_1fr] gap-3 rounded-md border border-subtle p-3 text-13"
                >
                  <span className="text-secondary">{step.position}</span>
                  <span className="text-primary">{documentText(step.action)}</span>
                  <span className="text-secondary">
                    {t("testing.execution.expected", { expected: documentText(step.expected_result) })}
                  </span>
                </li>
              ))}
              {!selected.test_case_version.steps.length && (
                <li className="text-13 text-secondary">{t("testing.execution.no_steps")}</li>
              )}
            </ol>
          </div>
          <label className="block text-12 font-semibold text-secondary uppercase">
            {t("testing.execution.actual")}
            <textarea
              value={actual}
              onChange={(event) => setActual(event.target.value)}
              className="font-normal mt-2 min-h-24 w-full resize-y rounded-md border border-subtle bg-surface-1 p-3 text-14 text-primary outline-none focus:border-accent-strong"
              placeholder={t("testing.execution.actual_placeholder")}
            />
          </label>
          {latestResult && (
            <div>
              <div className="flex items-center justify-between">
                <h4 className="text-12 font-semibold text-secondary uppercase">{t("testing.execution.evidence")}</h4>
                <label className="flex cursor-pointer items-center gap-1 text-11 text-accent-primary">
                  <Paperclip className="size-3.5" />
                  {attaching ? t("testing.execution.uploading") : t("testing.execution.attach")}
                  <input
                    type="file"
                    className="hidden"
                    disabled={attaching || run.status === "completed"}
                    onChange={async (event) => {
                      const file = event.target.files?.[0];
                      event.target.value = "";
                      if (!file) return;
                      setAttaching(true);
                      setAttachError(null);
                      try {
                        const created = await onAttach(selected.id, latestResult.id, file);
                        setAttachments((current) => [...current, created]);
                      } catch {
                        setAttachError(t("testing.execution.attach_failed"));
                      } finally {
                        setAttaching(false);
                      }
                    }}
                  />
                </label>
              </div>
              <p className="mt-1 text-11 text-tertiary">{t("testing.execution.evidence_hint")}</p>
              {attachments.length ? (
                <ul className="mt-2 space-y-1">
                  {attachments.map((item) => (
                    <li key={item.id} className="flex items-center gap-2 text-12">
                      <Paperclip className="size-3.5 shrink-0 text-tertiary" />
                      {item.asset_url ? (
                        <a
                          href={item.asset_url}
                          className="min-w-0 flex-1 truncate text-accent-primary hover:underline"
                        >
                          {item.name}
                        </a>
                      ) : (
                        <span className="min-w-0 flex-1 truncate text-primary">{item.name}</span>
                      )}
                      {run.status !== "completed" && (
                        <button
                          type="button"
                          aria-label={t("testing.execution.remove", { name: item.name })}
                          onClick={async () => {
                            await onDetach(selected.id, latestResult.id, item.id);
                            setAttachments((current) => current.filter((asset) => asset.id !== item.id));
                          }}
                          className="rounded p-0.5 text-tertiary hover:bg-layer-2 hover:text-primary"
                        >
                          <X className="size-3" />
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-11 text-tertiary">{t("testing.execution.no_evidence")}</p>
              )}
              {attachError && (
                <p role="alert" className="mt-1 text-11 text-danger-primary">
                  {attachError}
                </p>
              )}
            </div>
          )}
          {latestResult && (latestResult.status === "failed" || latestResult.status === "blocked") && (
            <div className="rounded-md border border-danger-subtle bg-danger-subtle/20 p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-12 font-semibold text-primary">{t("testing.execution.defect_heading")}</p>
                  <p className="mt-1 text-11 text-secondary">
                    {latestResult.defects.length
                      ? latestResult.defects
                          .map((defect) => `#${defect.sequence_id} ${defect.name} (${defect.state_group ?? "open"})`)
                          .join(", ")
                      : t("testing.execution.defect_hint")}
                  </p>
                </div>
                {!latestResult.defects.length && (
                  <Button
                    variant="error-outline"
                    disabled={creatingDefect}
                    onClick={async () => {
                      setCreatingDefect(true);
                      try {
                        await onCreateDefect(selected.id, latestResult.id);
                      } finally {
                        setCreatingDefect(false);
                      }
                    }}
                  >
                    <Bug className="size-4" /> {t("testing.execution.create_defect")}
                  </Button>
                )}
                {readyForRetest && (
                  <span className="rounded bg-success-subtle px-2 py-1 text-11 font-medium text-success-primary">
                    {t("testing.execution.ready_for_retest")}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>

        {run.status !== "completed" && (
          <div className="sticky bottom-0 mt-auto flex flex-wrap justify-end gap-2 border-t border-subtle bg-surface-1 pt-4">
            <Button variant="secondary" disabled={saving} onClick={() => void submit("skipped")}>
              <SkipForward className="size-4" /> {t("testing.execution.skip")}
            </Button>
            <Button variant="secondary" disabled={saving} onClick={() => void submit("blocked")}>
              <CircleSlash className="size-4" /> {t("testing.execution.block")}
            </Button>
            <Button variant="error-outline" disabled={saving} onClick={() => void submit("failed")}>
              <X className="size-4" /> {t("testing.execution.fail")}
            </Button>
            <Button variant="primary" disabled={saving} onClick={() => void submit("passed")}>
              <Check className="size-4" /> {t("testing.execution.pass")}
            </Button>
          </div>
        )}
      </div>
    </section>
  );
}
