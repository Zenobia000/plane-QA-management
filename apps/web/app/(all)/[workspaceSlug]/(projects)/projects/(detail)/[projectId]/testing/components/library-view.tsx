/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { orderBy } from "lodash-es";
import { Download, Link2, Plus, Save, Upload, X } from "lucide-react";
import { observer } from "mobx-react";
import { useNavigate, useParams, useSearchParams } from "react-router";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import type { TTestCase, TTestCaseInput } from "@plane/types";
import { ExistingIssuesListModal } from "@/components/core/modals/existing-issues-list-modal";
import { useTesting } from "@/hooks/store/use-testing";
import { findCaseBySequence, testingPath } from "../helpers";
import { FolderTree } from "./folder-tree";

type Props = { workspaceSlug: string; projectId: string };

/** CI tags what it creates, so the source is already on the case. */
const sourceOf = (testCase: TTestCase) => (testCase.current.tags.includes("automated") ? "automated" : "manual");

/**
 * A case CI created from an unmapped result arrives with no suite and no
 * requirement. Nothing surfaced them before, so they accumulated outside
 * coverage without ever being wrong enough to notice.
 */
const isUnfiled = (testCase: TTestCase) =>
  sourceOf(testCase) === "automated" && !testCase.folder_id && testCase.work_item_ids.length === 0;

const textValue = (value: Record<string, unknown>) =>
  typeof value.text === "string" ? value.text : Object.keys(value).length ? JSON.stringify(value) : "";

export const TestLibraryView = observer(function TestLibraryView({ workspaceSlug, projectId }: Props) {
  const { t } = useTranslation();
  const {
    cases,
    folders,
    loading,
    createCase,
    updateCase,
    createFolder,
    renameFolder,
    deleteFolder,
    linkWorkItem,
    unlinkWorkItem,
    exportLibraryCSV,
    importLibraryCSV,
  } = useTesting();
  const { sequence } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [title, setTitle] = useState("");
  const [linking, setLinking] = useState(false);
  const [draft, setDraft] = useState<TTestCaseInput>();
  const selectedFolder = searchParams.get("folder");
  const testFolders = orderBy(Object.values(folders), ["sort_order", "name"], ["asc", "asc"]);
  const testCases = orderBy(
    Object.values(cases).filter((item) => !selectedFolder || item.folder_id === selectedFolder),
    ["sequence"],
    ["asc"]
  );
  const selected = findCaseBySequence(cases, sequence);
  const unfiled = Object.values(cases).filter(isUnfiled);

  const openCase = (testCase: TTestCase) =>
    navigate(
      testingPath({ workspaceSlug, projectId, tab: "cases", sequence: testCase.sequence, folderId: selectedFolder })
    );

  // The addressed case drives the editor, so the draft is seeded from the URL
  // rather than from the click that got here -- a shared link must open the
  // same editor state. Re-seeds on version bump so a save shows the new version.
  useEffect(() => {
    if (!selected) {
      setDraft(undefined);
      return;
    }
    setDraft({
      title: selected.current.title,
      folder_id: selected.folder_id,
      description: selected.current.description,
      preconditions: selected.current.preconditions,
      priority: selected.current.priority,
      tags: selected.current.tags,
      steps: selected.current.steps.map((step) => ({ action: step.action, expected_result: step.expected_result })),
    });
    // Deliberately keyed on identity and version only: depending on `selected`
    // itself would re-seed on every store mutation and discard in-progress edits.
    // oxlint-disable-next-line exhaustive-deps
  }, [selected?.id, selected?.current_version]);

  const stepText = useMemo(
    () =>
      draft?.steps?.map((step) => `${textValue(step.action)} | ${textValue(step.expected_result)}`).join("\n") ?? "",
    [draft?.steps]
  );

  const handleCreate = async () => {
    if (!title.trim()) return;
    setSaving(true);
    try {
      const created = await createCase(workspaceSlug, projectId, {
        title: title.trim(),
        folder_id: selectedFolder,
      });
      setTitle("");
      setCreating(false);
      openCase(created);
    } finally {
      setSaving(false);
    }
  };

  if (loading)
    return (
      <div className="flex flex-1 items-center justify-center text-13 text-secondary">
        {t("testing.loading_library")}
      </div>
    );

  return (
    <section className="flex min-h-0 flex-1 overflow-hidden rounded-lg border border-subtle bg-surface-1">
      <FolderTree
        folders={testFolders}
        selectedFolder={selectedFolder}
        onSelect={(folderId) => navigate(testingPath({ workspaceSlug, projectId, tab: "cases", folderId }))}
        onCreate={async (name, parentId) => {
          await createFolder(workspaceSlug, projectId, name, parentId);
        }}
        onRename={async (folderId, name) => {
          await renameFolder(workspaceSlug, projectId, folderId, name);
        }}
        onDelete={async (folderId) => {
          await deleteFolder(workspaceSlug, projectId, folderId);
          if (selectedFolder === folderId) navigate(testingPath({ workspaceSlug, projectId, tab: "cases" }));
        }}
      />

      <div className="w-80 shrink-0 overflow-y-auto border-r border-subtle">
        <div className="flex items-center justify-between border-b border-subtle p-3">
          <div>
            <h1 className="text-14 font-semibold text-primary">{t("testing.cases.heading")}</h1>
            <p className="text-11 text-secondary">{t("testing.cases.count", { count: testCases.length })}</p>
          </div>
          <div className="flex gap-1">
            <Button
              variant="secondary"
              onClick={async () => {
                const csv = await exportLibraryCSV(workspaceSlug, projectId);
                const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
                const anchor = document.createElement("a");
                anchor.href = url;
                anchor.download = "plane-testing-library.csv";
                anchor.click();
                URL.revokeObjectURL(url);
              }}
              aria-label={t("testing.cases.export")}
            >
              <Download className="size-4" />
            </Button>
            <label
              className="flex h-8 cursor-pointer items-center rounded border border-subtle px-2 text-secondary hover:bg-layer-1"
              aria-label={t("testing.cases.import")}
            >
              <Upload className="size-4" />
              <input
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                onChange={async (event) => {
                  const file = event.target.files?.[0];
                  if (file) await importLibraryCSV(workspaceSlug, projectId, await file.text());
                  event.target.value = "";
                }}
              />
            </label>
            <Button variant="primary" onClick={() => setCreating(true)}>
              <Plus className="size-4" /> {t("testing.cases.add")}
            </Button>
          </div>
        </div>
        {unfiled.length > 0 && !selectedFolder && (
          <div className="border-b border-subtle bg-warning-subtle/40 p-3">
            <p className="text-12 font-medium text-primary">
              {t("testing.cases.orphans.heading", { count: unfiled.length })}
            </p>
            <p className="mt-1 text-11 text-secondary">{t("testing.cases.orphans.detail")}</p>
          </div>
        )}
        {creating && (
          <form
            className="border-b border-subtle p-3"
            onSubmit={(event) => {
              event.preventDefault();
              void handleCreate();
            }}
          >
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder={t("testing.cases.create_placeholder")}
              className="h-9 w-full rounded border border-subtle bg-surface-1 px-2 text-13 text-primary outline-none"
            />
            <div className="mt-2 flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                {t("testing.cases.cancel")}
              </Button>
              <Button type="submit" variant="primary" disabled={!title.trim() || saving}>
                {t("testing.cases.create")}
              </Button>
            </div>
          </form>
        )}
        {testCases.map((testCase) => (
          <button
            type="button"
            key={testCase.id}
            onClick={() => openCase(testCase)}
            className={`w-full border-b border-subtle p-3 text-left ${selected?.id === testCase.id ? "bg-layer-1" : "hover:bg-surface-2"}`}
          >
            <span className="text-10 font-medium text-tertiary">
              TC-{testCase.sequence} · v{testCase.current_version}
            </span>
            <span className="mt-1 block text-13 font-medium text-primary">{testCase.current.title}</span>
            <span className="mt-1 flex items-center gap-2 text-11 text-secondary">
              <span className="capitalize">{testCase.current.priority}</span>
              <span className="rounded border border-subtle px-1.5 py-0.5 text-10 text-tertiary">
                {t(`testing.cases.source.${sourceOf(testCase)}`)}
              </span>
            </span>
          </button>
        ))}
      </div>

      <div className="min-w-0 flex-1 overflow-y-auto p-5">
        {!selected || !draft ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-13 text-secondary">
            {sequence ? (
              <>
                <p>{t("testing.cases.not_found", { sequence })}</p>
                <Button
                  variant="secondary"
                  onClick={() => navigate(testingPath({ workspaceSlug, projectId, tab: "cases" }))}
                >
                  {t("testing.cases.back_to_list")}
                </Button>
              </>
            ) : (
              <p>{t("testing.cases.select_prompt")}</p>
            )}
          </div>
        ) : (
          <form
            className="space-y-4"
            onSubmit={async (event) => {
              event.preventDefault();
              setSaving(true);
              try {
                await updateCase(workspaceSlug, projectId, selected.id, draft);
              } finally {
                setSaving(false);
              }
            }}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <span className="text-11 text-tertiary">
                  {t("testing.cases.editing_publishes", {
                    sequence: selected.sequence,
                    version: selected.current_version + 1,
                  })}
                </span>
                <h2 className="mt-1 text-18 font-semibold text-primary">{t("testing.cases.detail_heading")}</h2>
              </div>
              <Button type="submit" variant="primary" disabled={saving}>
                <Save className="size-4" /> {t("testing.cases.save_version")}
              </Button>
            </div>
            <label className="block text-12 font-medium text-secondary">
              {t("testing.cases.title_label")}
              <input
                value={draft.title}
                onChange={(event) => setDraft({ ...draft, title: event.target.value })}
                className="mt-1 h-10 w-full rounded border border-subtle bg-surface-1 px-3 text-14 text-primary outline-none"
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-12 font-medium text-secondary">
                {t("testing.cases.suite_label")}
                <select
                  value={draft.folder_id ?? ""}
                  onChange={(event) => setDraft({ ...draft, folder_id: event.target.value || null })}
                  className="mt-1 h-10 w-full rounded border border-subtle bg-surface-1 px-2 text-13 text-primary"
                >
                  <option value="">{t("testing.cases.unfiled")}</option>
                  {testFolders.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-12 font-medium text-secondary">
                {t("testing.cases.priority_label")}
                <select
                  value={draft.priority}
                  onChange={(event) =>
                    setDraft({ ...draft, priority: event.target.value as TTestCaseInput["priority"] })
                  }
                  className="mt-1 h-10 w-full rounded border border-subtle bg-surface-1 px-2 text-13 text-primary"
                >
                  {["none", "low", "medium", "high", "urgent"].map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </select>
              </label>
            </div>
            <label className="block text-12 font-medium text-secondary">
              {t("testing.cases.given_label")}
              <textarea
                value={textValue(draft.preconditions ?? {})}
                onChange={(event) => setDraft({ ...draft, preconditions: { text: event.target.value } })}
                className="mt-1 min-h-20 w-full rounded border border-subtle bg-surface-1 p-3 text-13 text-primary outline-none"
              />
            </label>
            <label className="block text-12 font-medium text-secondary">
              {t("testing.cases.steps_label")}{" "}
              <span className="font-normal text-tertiary">({t("testing.cases.steps_hint")})</span>
              <textarea
                value={stepText}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    steps: event.target.value
                      .split("\n")
                      .filter(Boolean)
                      .map((line) => {
                        const [action, expected = ""] = line.split("|");
                        return { action: { text: action.trim() }, expected_result: { text: expected.trim() } };
                      }),
                  })
                }
                className="font-mono mt-1 min-h-32 w-full rounded border border-subtle bg-surface-1 p-3 text-12 text-primary outline-none"
              />
            </label>
            <div className="rounded border border-subtle p-3">
              <p className="text-12 font-medium text-secondary">{t("testing.cases.traceability")}</p>
              {selected.work_items.length ? (
                <div className="mt-2 flex flex-wrap gap-2">
                  {selected.work_items.map((item) => (
                    <span
                      key={item.id}
                      className="inline-flex items-center gap-1.5 rounded border border-subtle bg-surface-2 py-1 pr-1 pl-2 text-11"
                    >
                      <a
                        href={`/${workspaceSlug}/projects/${projectId}/issues/${item.id}`}
                        className="text-accent-primary hover:underline"
                      >
                        #{item.sequence_id} {item.name}
                      </a>
                      <button
                        type="button"
                        aria-label={t("testing.cases.unlink", { name: item.name })}
                        onClick={() => void unlinkWorkItem(workspaceSlug, projectId, selected.id, item.id)}
                        className="rounded p-0.5 text-tertiary hover:bg-layer-2 hover:text-primary"
                      >
                        <X className="size-3" />
                      </button>
                    </span>
                  ))}
                </div>
              ) : (
                <p className="mt-1 text-11 text-tertiary">{t("testing.cases.traceability_empty")}</p>
              )}
              <div className="mt-2">
                {/* Pasting a UUID was the only way to link a requirement; the work-item
                    picker used by relations everywhere else does the same job by search. */}
                <Button type="button" variant="secondary" onClick={() => setLinking(true)}>
                  <Link2 className="size-4" /> {t("testing.cases.link_requirement")}
                </Button>
              </div>
            </div>
            <div className="rounded border border-subtle p-3">
              <p className="text-12 font-medium text-secondary">{t("testing.cases.executions")}</p>
              {selected.executions.length ? (
                <ul className="mt-2 space-y-1">
                  {selected.executions.map((execution) => (
                    <li key={execution.run_case_id} className="flex items-center gap-2 text-11">
                      <span
                        className={`w-14 shrink-0 rounded px-1.5 py-0.5 text-center text-10 font-medium ${
                          execution.latest_status === "failed" || execution.latest_status === "blocked"
                            ? "bg-danger-subtle text-danger-primary"
                            : execution.latest_status === "passed"
                              ? "bg-success-subtle text-success-primary"
                              : "bg-layer-2 text-secondary"
                        }`}
                      >
                        {t(`testing.status.${execution.latest_status}`)}
                      </span>
                      <a
                        href={testingPath({
                          workspaceSlug,
                          projectId,
                          tab: "runs",
                          runId: execution.run_id,
                          runCaseId: execution.run_case_id,
                        })}
                        className="min-w-0 flex-1 truncate text-accent-primary hover:underline"
                      >
                        {execution.run_name}
                      </a>
                      <span className="shrink-0 text-tertiary">
                        {execution.build || "—"} · {t("testing.cases.pinned", { version: execution.pinned_version })}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1 text-11 text-tertiary">{t("testing.cases.executions_empty")}</p>
              )}
            </div>
          </form>
        )}
      </div>
      {selected && (
        <ExistingIssuesListModal
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          isOpen={linking}
          handleClose={() => setLinking(false)}
          searchParams={{}}
          selectedWorkItemIds={selected.work_item_ids}
          handleOnSubmit={async (items) => {
            await Promise.all(items.map((item) => linkWorkItem(workspaceSlug, projectId, selected.id, item.id)));
            setLinking(false);
          }}
        />
      )}
    </section>
  );
});
