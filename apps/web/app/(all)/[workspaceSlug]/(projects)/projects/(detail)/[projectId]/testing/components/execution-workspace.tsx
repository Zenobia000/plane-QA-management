/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { Bug, Check, CircleSlash, Lock, SkipForward, X } from "lucide-react";
import { Button } from "@plane/propel/button";
import type { TTestResultInput, TTestResultStatus, TTestRun } from "@plane/types";

type Props = {
  run: TTestRun;
  /** Absent means "no case addressed yet" -- the first open one is shown. */
  selectedRunCaseId?: string;
  onSelectRunCase: (runCaseId: string, options?: { replace?: boolean }) => void;
  onBack: () => void;
  onResult: (runCaseId: string, input: TTestResultInput) => Promise<void>;
  onClose: () => Promise<void>;
  onCreateDefect: (runCaseId: string, resultId: string) => Promise<unknown>;
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
}: Props) {
  const [actual, setActual] = useState("");
  const [saving, setSaving] = useState(false);
  const [creatingDefect, setCreatingDefect] = useState(false);
  const selected = useMemo(() => {
    const addressed = selectedRunCaseId && run.run_cases.find((item) => item.id === selectedRunCaseId);
    if (addressed) return addressed;
    return run.run_cases.find((item) => item.latest_status === "open") ?? run.run_cases[0];
  }, [run.run_cases, selectedRunCaseId]);
  const latestResult = selected?.results.at(-1);
  const readyForRetest =
    !!latestResult?.defects.length &&
    latestResult.defects.every((defect) => defect.state_group === "completed" || defect.state_group === "cancelled");

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
            ← All runs
          </button>
          <h2 className="mt-2 text-14 font-semibold text-primary">{run.name}</h2>
          <p className="mt-1 text-11 text-secondary">
            {run.progress.total - run.progress.open}/{run.progress.total} executed
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
              Case {selected.position} · v{selected.test_case_version.version}
            </div>
            <h3 className="mt-1 text-20 font-semibold text-primary">{selected.test_case_version.title}</h3>
          </div>
          {run.status === "completed" ? (
            <span className="flex items-center gap-1 rounded bg-layer-2 px-2 py-1 text-11 text-secondary">
              <Lock className="size-3" /> Closed
            </span>
          ) : (
            <Button variant="secondary" onClick={() => void onClose()}>
              Close run
            </Button>
          )}
        </div>

        <div className="mt-6 space-y-5">
          <div>
            <h4 className="text-12 font-semibold text-secondary uppercase">Preconditions</h4>
            <p className="mt-2 text-14 text-primary">{documentText(selected.test_case_version.preconditions)}</p>
          </div>
          <div>
            <h4 className="text-12 font-semibold text-secondary uppercase">Steps</h4>
            <ol className="mt-2 space-y-2">
              {selected.test_case_version.steps.map((step) => (
                <li
                  key={step.id}
                  className="grid grid-cols-[2rem_1fr_1fr] gap-3 rounded-md border border-subtle p-3 text-13"
                >
                  <span className="text-secondary">{step.position}</span>
                  <span className="text-primary">{documentText(step.action)}</span>
                  <span className="text-secondary">Expected: {documentText(step.expected_result)}</span>
                </li>
              ))}
              {!selected.test_case_version.steps.length && (
                <li className="text-13 text-secondary">No structured steps.</li>
              )}
            </ol>
          </div>
          <label className="block text-12 font-semibold text-secondary uppercase">
            Actual result
            <textarea
              value={actual}
              onChange={(event) => setActual(event.target.value)}
              className="font-normal mt-2 min-h-24 w-full resize-y rounded-md border border-subtle bg-surface-1 p-3 text-14 text-primary outline-none focus:border-accent-strong"
              placeholder="Capture observations, especially for failures or blockers."
            />
          </label>
          {latestResult && (latestResult.status === "failed" || latestResult.status === "blocked") && (
            <div className="rounded-md border border-danger-subtle bg-danger-subtle/20 p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-12 font-semibold text-primary">Defect tracking</p>
                  <p className="mt-1 text-11 text-secondary">
                    {latestResult.defects.length
                      ? latestResult.defects
                          .map((defect) => `#${defect.sequence_id} ${defect.name} (${defect.state_group ?? "open"})`)
                          .join(", ")
                      : "Create a Plane work item with the run, build, steps, and actual result attached."}
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
                    <Bug className="size-4" /> Create defect
                  </Button>
                )}
                {readyForRetest && (
                  <span className="rounded bg-success-subtle px-2 py-1 text-11 font-medium text-success-primary">
                    Ready for retest · record a new result below
                  </span>
                )}
              </div>
            </div>
          )}
        </div>

        {run.status !== "completed" && (
          <div className="sticky bottom-0 mt-auto flex flex-wrap justify-end gap-2 border-t border-subtle bg-surface-1 pt-4">
            <Button variant="secondary" disabled={saving} onClick={() => void submit("skipped")}>
              <SkipForward className="size-4" /> Skip (S)
            </Button>
            <Button variant="secondary" disabled={saving} onClick={() => void submit("blocked")}>
              <CircleSlash className="size-4" /> Block (B)
            </Button>
            <Button variant="error-outline" disabled={saving} onClick={() => void submit("failed")}>
              <X className="size-4" /> Fail (F)
            </Button>
            <Button variant="primary" disabled={saving} onClick={() => void submit("passed")}>
              <Check className="size-4" /> Pass (P)
            </Button>
          </div>
        )}
      </div>
    </section>
  );
}
