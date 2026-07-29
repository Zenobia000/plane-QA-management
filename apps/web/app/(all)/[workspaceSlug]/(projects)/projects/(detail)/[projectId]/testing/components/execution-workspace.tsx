/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { Bug, Check, CircleSlash, Lock, Paperclip, SkipForward, X } from "lucide-react";
import remarkGfm from "remark-gfm";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import type { TTestResult, TTestResultAttachment, TTestResultInput, TTestResultStatus, TTestRun } from "@plane/types";
import { AlertModalCore } from "@plane/ui";
import { MarkdownRenderer } from "@/components/ui/markdown-to-component";
import { EvidenceComposer, type TResultEvidenceDraftFile } from "./evidence-composer";
import { WorkItemLink } from "./work-item-link";

type Props = {
  run: TTestRun;
  /** Both only so a defect can be opened; every interaction still goes through a callback. */
  workspaceSlug: string;
  projectId: string;
  /** Absent means "no case addressed yet" -- the first open one is shown. */
  selectedRunCaseId?: string;
  onSelectRunCase: (runCaseId: string, options?: { replace?: boolean }) => void;
  onBack: () => void;
  onResult: (runCaseId: string, input: TTestResultInput) => Promise<TTestResult>;
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

type TResultEvidenceDraft = {
  actual: string;
  files: TResultEvidenceDraftFile[];
  recordedResultId?: string;
  error?: string;
};

const emptyEvidenceDraft = (): TResultEvidenceDraft => ({ actual: "", files: [] });

/**
 * P/F/B/S are destructive shortcuts because results cannot be edited later.
 * Keep them inert in native inputs and any present or future rich-text editor.
 */
export const isEvidenceTypingTarget = (target: EventTarget | null) => {
  const element = target as HTMLElement | null;
  const tagName = element?.tagName?.toLowerCase();
  return (
    tagName === "input" ||
    tagName === "textarea" ||
    tagName === "select" ||
    Boolean(element?.isContentEditable) ||
    Boolean(element?.closest?.("[contenteditable='true'], [data-evidence-editor]"))
  );
};

export const uploadResultEvidence = async (
  files: TResultEvidenceDraftFile[],
  upload: (file: TResultEvidenceDraftFile) => Promise<TTestResultAttachment>
) => {
  const settled = await Promise.allSettled(files.map(upload));
  return {
    uploaded: settled.flatMap((result) => (result.status === "fulfilled" ? [result.value] : [])),
    failed: files.filter((_, index) => settled[index].status === "rejected"),
  };
};

export function ExecutionWorkspace({
  run,
  workspaceSlug,
  projectId,
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
  const selected = useMemo(() => {
    const addressed = selectedRunCaseId && run.run_cases.find((item) => item.id === selectedRunCaseId);
    if (addressed) return addressed;
    return run.run_cases.find((item) => item.latest_status === "open") ?? run.run_cases[0];
  }, [run.run_cases, selectedRunCaseId]);
  const [drafts, setDrafts] = useState<Record<string, TResultEvidenceDraft>>({});
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const [closeConfirmationOpen, setCloseConfirmationOpen] = useState(false);
  const [closing, setClosing] = useState(false);
  const [creatingDefect, setCreatingDefect] = useState(false);
  const [attachments, setAttachments] = useState<TTestResultAttachment[]>([]);
  const [attaching, setAttaching] = useState(false);
  const [attachError, setAttachError] = useState<string | null>(null);
  const activeDraft = selected ? (drafts[selected.id] ?? emptyEvidenceDraft()) : emptyEvidenceDraft();
  const executionHistory = selected ? selected.results.toReversed() : [];
  const latestResult = selected?.results.at(-1);
  const readyForRetest =
    !!latestResult?.defects.length &&
    latestResult.defects.every((defect) => defect.state_group === "completed" || defect.state_group === "cancelled");

  const updateDraft = (runCaseId: string, updater: (draft: TResultEvidenceDraft) => TResultEvidenceDraft) => {
    setDrafts((current) => ({
      ...current,
      [runCaseId]: updater(current[runCaseId] ?? emptyEvidenceDraft()),
    }));
  };

  const finishDraft = (runCaseId: string) => {
    setDrafts((current) => {
      const nextDrafts = { ...current };
      delete nextDrafts[runCaseId];
      return nextDrafts;
    });
    const currentRunCase = run.run_cases.find((item) => item.id === runCaseId);
    const next = run.run_cases.find(
      (item) => currentRunCase && item.position > currentRunCase.position && item.latest_status === "open"
    );
    if (next) onSelectRunCase(next.id, { replace: true });
  };

  const uploadDraftFiles = async (runCaseId: string, resultId: string, files: TResultEvidenceDraftFile[]) => {
    updateDraft(runCaseId, (draft) => ({
      ...draft,
      error: undefined,
      files: draft.files.map((file) =>
        files.some((candidate) => candidate.id === file.id) ? { ...file, status: "uploading", error: undefined } : file
      ),
    }));

    const { uploaded, failed } = await uploadResultEvidence(files, (item) => onAttach(runCaseId, resultId, item.file));
    const failedIds = new Set(failed.map((file) => file.id));
    if (uploaded.length) {
      setAttachments((current) => [
        ...current,
        ...uploaded.filter((item) => !current.some((currentItem) => currentItem.id === item.id)),
      ]);
    }

    updateDraft(runCaseId, (draft) => ({
      ...draft,
      recordedResultId: failedIds.size ? resultId : undefined,
      error: failedIds.size ? t("testing.execution.result_saved_upload_failed", { count: failedIds.size }) : undefined,
      files: draft.files
        .filter((file) => failedIds.has(file.id))
        .map((file) => ({
          id: file.id,
          file: file.file,
          status: "failed",
          error: t("testing.execution.attach_failed"),
        })),
    }));

    try {
      const currentAttachments = await onListAttachments(runCaseId, resultId);
      if (selected?.id === runCaseId) setAttachments(currentAttachments);
    } catch {
      // Upload results above remain authoritative; a later result selection reloads the list.
    }
    return failedIds.size === 0;
  };

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
      if (isEvidenceTypingTarget(event.target) || savingRef.current || activeDraft.recordedResultId) return;
      const shortcuts: Record<string, TTestResultStatus> = { p: "passed", f: "failed", b: "blocked", s: "skipped" };
      const status = shortcuts[event.key.toLowerCase()];
      if (status && selected && run.status !== "completed") void submit(status);
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  });

  const submit = async (status: TTestResultStatus) => {
    if (!selected || run.status === "completed" || savingRef.current || activeDraft.recordedResultId) return;
    savingRef.current = true;
    setSaving(true);
    updateDraft(selected.id, (draft) => ({ ...draft, error: undefined }));
    try {
      const result = await onResult(selected.id, {
        status,
        actual_result: activeDraft.actual.trim() ? { text: activeDraft.actual, format: "markdown" } : {},
      });
      updateDraft(selected.id, (draft) => ({ ...draft, recordedResultId: result.id }));
      if (!activeDraft.files.length || (await uploadDraftFiles(selected.id, result.id, activeDraft.files))) {
        // Advancing replaces rather than pushes: results are append-only, so a
        // history entry per recorded result would offer a Back that undoes nothing.
        finishDraft(selected.id);
      }
    } catch {
      updateDraft(selected.id, (draft) => ({ ...draft, error: t("testing.execution.result_save_failed") }));
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  };

  const retryDraftUploads = async () => {
    if (!selected || !activeDraft.recordedResultId || savingRef.current) return;
    if (!activeDraft.files.length) {
      finishDraft(selected.id);
      return;
    }
    savingRef.current = true;
    setSaving(true);
    try {
      if (await uploadDraftFiles(selected.id, activeDraft.recordedResultId, activeDraft.files)) {
        finishDraft(selected.id);
      }
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  };

  const closeRun = async () => {
    setClosing(true);
    try {
      await onClose();
      setCloseConfirmationOpen(false);
    } finally {
      setClosing(false);
    }
  };

  if (!selected) return null;

  return (
    <>
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
              disabled={saving}
              onClick={() => onSelectRunCase(runCase.id)}
              className={`flex w-full items-center gap-2 border-b border-subtle px-3 py-3 text-left ${
                selected.id === runCase.id ? "bg-surface-1" : "hover:bg-layer-1"
              } disabled:cursor-wait disabled:opacity-60`}
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
              <Button variant="secondary" disabled={saving || attaching} onClick={() => setCloseConfirmationOpen(true)}>
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
            {executionHistory.length > 0 && (
              <div>
                <h4 className="text-12 font-semibold text-secondary uppercase">Execution history</h4>
                <ul className="mt-2 space-y-2">
                  {executionHistory.map((result) => (
                    <li key={result.id} className="rounded-md border border-subtle p-3 text-12">
                      <div className="flex items-center justify-between gap-3">
                        <span className={`rounded px-1.5 py-0.5 text-10 font-medium ${statusStyle[result.status]}`}>
                          {t(`testing.status.${result.status}`)}
                        </span>
                        <time className="text-tertiary">{new Date(result.created_at).toLocaleString()}</time>
                      </div>
                      <div className="mt-2">
                        <span className="text-11 font-medium text-tertiary">{t("testing.execution.actual")}</span>
                        <div className="mt-1 rounded bg-surface-2 p-2">
                          <MarkdownRenderer
                            markdown={documentText(result.actual_result)}
                            options={{ remarkPlugins: [remarkGfm] }}
                          />
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {run.status !== "completed" && (
              <EvidenceComposer
                value={activeDraft.actual}
                files={activeDraft.files}
                disabled={saving}
                readOnly={Boolean(activeDraft.recordedResultId)}
                error={activeDraft.error}
                onChange={(actual) => updateDraft(selected.id, (draft) => ({ ...draft, actual, error: undefined }))}
                onFilesChange={(files) => updateDraft(selected.id, (draft) => ({ ...draft, files, error: undefined }))}
              />
            )}
            {latestResult && (
              <div>
                <div className="flex items-center justify-between">
                  <h4 className="text-12 font-semibold text-secondary uppercase">{t("testing.execution.evidence")}</h4>
                  <label className="flex cursor-pointer items-center gap-1 text-11 text-accent-primary">
                    <Paperclip className="size-3.5" />
                    {attaching ? t("testing.execution.uploading") : t("testing.execution.attach")}
                    <input
                      type="file"
                      multiple
                      className="hidden"
                      disabled={attaching || run.status === "completed"}
                      onChange={async (event) => {
                        const files = Array.from(event.target.files ?? []);
                        event.target.value = "";
                        if (!files.length) return;
                        setAttaching(true);
                        setAttachError(null);
                        try {
                          const settled = await Promise.allSettled(
                            files.map((file) => onAttach(selected.id, latestResult.id, file))
                          );
                          const created = settled.flatMap((result) =>
                            result.status === "fulfilled" ? [result.value] : []
                          );
                          setAttachments((current) => [
                            ...current,
                            ...created.filter((item) => !current.some((currentItem) => currentItem.id === item.id)),
                          ]);
                          if (settled.some((result) => result.status === "rejected")) {
                            setAttachError(t("testing.execution.attach_failed"));
                          }
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
                    {latestResult.defects.length ? (
                      <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-11">
                        {latestResult.defects.map((defect) => (
                          <li key={defect.id}>
                            <WorkItemLink
                              workspaceSlug={workspaceSlug}
                              projectId={projectId}
                              issueId={defect.id}
                              sequenceId={defect.sequence_id}
                              className="text-accent-primary hover:underline"
                            >
                              #{defect.sequence_id} {defect.name}
                            </WorkItemLink>
                            <span className="ml-1 text-tertiary">({defect.state_group ?? "open"})</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-1 text-11 text-secondary">{t("testing.execution.defect_hint")}</p>
                    )}
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

          {run.status !== "completed" && !activeDraft.recordedResultId && (
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
          {run.status !== "completed" && activeDraft.recordedResultId && (
            <div className="sticky bottom-0 mt-auto flex flex-wrap items-center justify-between gap-3 border-t border-subtle bg-surface-1 pt-4">
              <p className="text-11 text-secondary">{t("testing.execution.result_saved_retry_hint")}</p>
              <div className="flex flex-wrap justify-end gap-2">
                <Button
                  variant="secondary"
                  disabled={saving}
                  onClick={() => {
                    const runCaseId = selected.id;
                    finishDraft(runCaseId);
                  }}
                >
                  {t("testing.execution.continue_without_files")}
                </Button>
                <Button
                  variant="primary"
                  disabled={saving || !activeDraft.files.length}
                  onClick={() => void retryDraftUploads()}
                >
                  <Paperclip className="size-4" /> {t("testing.execution.retry_uploads")}
                </Button>
              </div>
            </div>
          )}
        </div>
      </section>
      <AlertModalCore
        handleClose={() => setCloseConfirmationOpen(false)}
        handleSubmit={() => void closeRun()}
        isSubmitting={closing}
        isOpen={closeConfirmationOpen}
        title="Close test run"
        variant="primary"
        primaryButtonText={{ default: "Close run", loading: "Closing" }}
        content="Closing the run preserves its evidence and prevents any new results from being recorded."
      />
    </>
  );
}
