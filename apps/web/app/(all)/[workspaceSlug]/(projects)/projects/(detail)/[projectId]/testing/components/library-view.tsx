/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { orderBy } from "lodash-es";
import {
  Archive,
  Download,
  FileText,
  ImageIcon,
  Link2,
  Paperclip,
  Plus,
  Save,
  Search,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { observer } from "mobx-react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type {
  TTestCase,
  TTestCaseInput,
  TTestCaseType,
  TTestingExportFormat,
  TTestingSearchResponse,
  TTestingSearchResult,
  TTestingSearchScope,
  TTestThreshold,
} from "@plane/types";
import { AlertModalCore, CustomMenu } from "@plane/ui";
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

const errorMessage = (error: unknown, fallback: string) => {
  if (!error || typeof error !== "object") return fallback;
  const value = error as { detail?: unknown; error?: unknown };
  if (typeof value.detail === "string") return value.detail;
  if (typeof value.error === "string") return value.error;
  if (value.error && typeof value.error === "object" && "message" in value.error) {
    const message = (value.error as { message?: unknown }).message;
    if (typeof message === "string") return message;
  }
  return fallback;
};

type TTestCaseTraceabilityProps = {
  testCase: TTestCase;
  workspaceSlug: string;
  projectId: string;
  onLinkRequirement: () => void;
  onUnlinkWorkItem: (workItemId: string) => void;
};

export function TestCaseTraceability({
  testCase,
  workspaceSlug,
  projectId,
  onLinkRequirement,
  onUnlinkWorkItem,
}: TTestCaseTraceabilityProps) {
  const { t } = useTranslation();

  return (
    <div className="rounded border border-subtle p-3">
      <p className="text-12 font-medium text-secondary">{t("testing.cases.traceability")}</p>
      {testCase.work_items.length ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {testCase.work_items.map((item) => (
            <span
              key={item.id}
              className="inline-flex items-center gap-1.5 rounded border border-subtle bg-surface-2 py-1 pr-1 pl-2 text-11"
            >
              <Link
                to={`/${workspaceSlug}/projects/${projectId}/issues/${item.id}`}
                className="text-accent-primary hover:underline"
              >
                #{item.sequence_id} {item.name}
              </Link>
              <button
                type="button"
                aria-label={t("testing.cases.unlink", { name: item.name })}
                onClick={() => onUnlinkWorkItem(item.id)}
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
        <Button type="button" variant="secondary" onClick={onLinkRequirement}>
          <Link2 className="size-4" /> {t("testing.cases.link_requirement")}
        </Button>
      </div>
    </div>
  );
}

type TTestCaseExecutionHistoryProps = {
  testCase: TTestCase;
  workspaceSlug: string;
  projectId: string;
};

export function TestCaseExecutionHistory({ testCase, workspaceSlug, projectId }: TTestCaseExecutionHistoryProps) {
  const { t } = useTranslation();

  return (
    <div className="rounded border border-subtle p-3">
      <p className="text-12 font-medium text-secondary">{t("testing.cases.executions")}</p>
      {testCase.executions.length ? (
        <ul className="mt-2 space-y-1">
          {testCase.executions.map((execution) => (
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
              <Link
                to={testingPath({
                  workspaceSlug,
                  projectId,
                  tab: "runs",
                  runId: execution.run_id,
                  runCaseId: execution.run_case_id,
                })}
                className="min-w-0 flex-1 truncate text-accent-primary hover:underline"
              >
                {execution.run_name}
              </Link>
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
  );
}

type TTestLibrarySearchResultProps = {
  result: TTestingSearchResult;
  testCase?: TTestCase;
  workspaceSlug: string;
  projectId: string;
  onOpenCase: (testCase: TTestCase) => void;
};

export function TestLibrarySearchResult({
  result,
  testCase,
  workspaceSlug,
  projectId,
  onOpenCase,
}: TTestLibrarySearchResultProps) {
  const content = (
    <>
      <span className="text-10 font-medium text-tertiary">
        {result.identifier} · {result.kind === "test_case" ? "Test case" : "Work item"}
      </span>
      <span className="mt-1 block truncate text-13 font-medium text-primary">{result.title}</span>
      <span className="mt-1 block truncate text-11 text-secondary capitalize">
        {result.priority} · {result.status}
      </span>
    </>
  );

  if (testCase)
    return (
      <button
        type="button"
        onClick={() => onOpenCase(testCase)}
        className="block w-full border-b border-subtle p-3 text-left hover:bg-surface-2"
      >
        {content}
      </button>
    );

  return (
    <Link
      to={`/${workspaceSlug}/projects/${projectId}/issues/${result.id}`}
      className="block border-b border-subtle p-3 hover:bg-surface-2"
    >
      {content}
    </Link>
  );
}

export const TestLibraryView = observer(function TestLibraryView({ workspaceSlug, projectId }: Props) {
  const { t } = useTranslation();
  const {
    cases,
    attachments,
    folders,
    loading,
    createCase,
    updateCase,
    archiveCase,
    createFolder,
    renameFolder,
    deleteFolder,
    linkWorkItem,
    unlinkWorkItem,
    searchLibrary,
    exportSearch,
    fetchAttachments,
    uploadAttachment,
    deleteAttachment,
    exportLibraryCSV,
    importLibraryCSV,
  } = useTesting();
  const { sequence } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [searching, setSearching] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [archivingCase, setArchivingCase] = useState(false);
  const [caseArchiveId, setCaseArchiveId] = useState<string>();
  const [title, setTitle] = useState("");
  const [linking, setLinking] = useState(false);
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState<TTestingSearchScope>("all");
  const [searchResponse, setSearchResponse] = useState<TTestingSearchResponse>();
  const [draft, setDraft] = useState<TTestCaseInput>();
  const selectedFolder = searchParams.get("folder");
  const testFolders = orderBy(Object.values(folders), ["sort_order", "name"], ["asc", "asc"]);
  const testCases = orderBy(
    Object.values(cases).filter((item) => !selectedFolder || item.folder_id === selectedFolder),
    ["sequence"],
    ["asc"]
  );
  const selected = findCaseBySequence(cases, sequence);
  const selectedAttachments = selected ? (attachments[selected.id] ?? []) : [];
  const caseToArchive = caseArchiveId ? cases[caseArchiveId] : undefined;
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
      case_type: selected.current.case_type,
      tags: selected.current.tags,
      steps: selected.current.steps.map((step) => ({ action: step.action, expected_result: step.expected_result })),
    });
    void fetchAttachments(workspaceSlug, projectId, selected.id).catch((error) => {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Attachments could not be loaded",
        message: errorMessage(error, "Please try again."),
      });
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

  const handleArchiveCase = async () => {
    if (!caseToArchive) return;
    setArchivingCase(true);
    try {
      await archiveCase(workspaceSlug, projectId, caseToArchive.id);
      setCaseArchiveId(undefined);
      navigate(testingPath({ workspaceSlug, projectId, tab: "cases", folderId: selectedFolder }));
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Test case archived",
        message: `TC-${caseToArchive.sequence} was removed from the active library.`,
      });
    } catch (error) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Test case could not be archived",
        message: errorMessage(error, "Please try again."),
      });
    } finally {
      setArchivingCase(false);
    }
  };

  const handleSearch = async () => {
    setSearching(true);
    try {
      setSearchResponse(await searchLibrary(workspaceSlug, projectId, query.trim(), scope));
    } catch (error) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Search could not be completed",
        message: errorMessage(error, "Check the query syntax and try again."),
      });
    } finally {
      setSearching(false);
    }
  };

  const handleExport = async (format: TTestingExportFormat) => {
    try {
      const blob = await exportSearch(workspaceSlug, projectId, query.trim(), scope, format);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `plane-testing-search.${format === "excel" ? "xlsx" : format}`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Export could not be created",
        message: errorMessage(error, "Please try again."),
      });
    }
  };

  if (loading)
    return (
      <div className="flex flex-1 items-center justify-center text-13 text-secondary">
        {t("testing.loading_library")}
      </div>
    );

  return (
    <>
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
              <p className="text-11 text-secondary">
                {searchResponse
                  ? `${searchResponse.count} matches`
                  : t("testing.cases.count", { count: testCases.length })}
              </p>
            </div>
            <div className="flex gap-1">
              <CustomMenu
                customButton={<Download className="size-4" />}
                customButtonClassName="flex h-8 items-center rounded border border-subtle px-2 text-secondary hover:bg-layer-1"
                ariaLabel={t("common.export")}
                placement="bottom-end"
                closeOnSelect
              >
                <p className="px-2 pb-1 text-10 font-medium text-tertiary uppercase">Test library</p>
                <CustomMenu.MenuItem
                  className="flex items-center gap-2"
                  onClick={async () => {
                    const csv = await exportLibraryCSV(workspaceSlug, projectId);
                    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
                    const anchor = document.createElement("a");
                    anchor.href = url;
                    anchor.download = "plane-testing-library.csv";
                    anchor.click();
                    URL.revokeObjectURL(url);
                  }}
                >
                  <FileText className="size-3.5" /> CSV backup
                </CustomMenu.MenuItem>
                <hr className="my-2 border-subtle" />
                <p className="px-2 pb-1 text-10 font-medium text-tertiary uppercase">Current search</p>
                {(["csv", "html", "excel"] as const).map((format) => (
                  <CustomMenu.MenuItem
                    key={format}
                    className="flex items-center gap-2"
                    onClick={() => void handleExport(format)}
                  >
                    <Download className="size-3.5" />
                    {format === "excel" ? "Excel (.xlsx)" : format.toUpperCase()}
                  </CustomMenu.MenuItem>
                ))}
              </CustomMenu>
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
          <form
            className="space-y-2 border-b border-subtle p-3"
            onSubmit={(event) => {
              event.preventDefault();
              void handleSearch();
            }}
          >
            <div className="flex gap-1">
              <div className="relative min-w-0 flex-1">
                <Search className="absolute top-2.5 left-2 size-3.5 text-tertiary" />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  aria-label="Search test cases and work items"
                  placeholder="Search cases and work items"
                  className="h-9 w-full rounded border border-subtle bg-surface-1 pr-2 pl-7 text-12 text-primary outline-none"
                />
              </div>
              <Button type="submit" variant="secondary" disabled={searching}>
                {searching ? "…" : "Search"}
              </Button>
            </div>
            <div className="flex flex-wrap items-center gap-1">
              <select
                value={scope}
                onChange={(event) => setScope(event.target.value as TTestingSearchScope)}
                className="h-8 rounded border border-subtle bg-surface-1 px-2 text-11 text-primary"
              >
                <option value="all">Cases + Work items</option>
                <option value="test_cases">Test cases</option>
                <option value="work_items">Work items</option>
              </select>
              {searchResponse && (
                <Button type="button" variant="secondary" onClick={() => setSearchResponse(undefined)}>
                  Clear
                </Button>
              )}
            </div>
            <p className="text-10 text-tertiary">
              Controlled query fields: type, id, title, priority, status, tag, folder.
            </p>
          </form>
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
          {searchResponse
            ? searchResponse.results.map((result) => (
                <TestLibrarySearchResult
                  key={`${result.kind}-${result.id}`}
                  result={result}
                  testCase={result.kind === "test_case" ? cases[result.id] : undefined}
                  workspaceSlug={workspaceSlug}
                  projectId={projectId}
                  onOpenCase={openCase}
                />
              ))
            : testCases.map((testCase) => (
                <div
                  key={testCase.id}
                  className={`group flex w-full items-center border-b border-subtle ${selected?.id === testCase.id ? "bg-layer-1" : "hover:bg-surface-2"}`}
                >
                  <button type="button" onClick={() => openCase(testCase)} className="min-w-0 flex-1 p-3 text-left">
                    <span className="text-10 font-medium text-tertiary">
                      TC-{testCase.sequence} · v{testCase.current_version}
                    </span>
                    <span className="mt-1 block truncate text-13 font-medium text-primary">
                      {testCase.current.title}
                    </span>
                    <span className="mt-1 flex items-center gap-2 text-11 text-secondary">
                      <span className="capitalize">{testCase.current.priority}</span>
                      <span className="rounded border border-subtle px-1.5 py-0.5 text-10 text-tertiary">
                        {t(`testing.cases.source.${sourceOf(testCase)}`)}
                      </span>
                      {testCase.current.case_type !== "functional" && (
                        <span className="rounded border border-accent-strong px-1.5 py-0.5 text-10 text-accent-primary">
                          {t(`testing.cases.type.${testCase.current.case_type}`)}
                        </span>
                      )}
                    </span>
                  </button>
                  <button
                    type="button"
                    aria-label={`Archive TC-${testCase.sequence}`}
                    onClick={() => setCaseArchiveId(testCase.id)}
                    className="mr-2 rounded p-1.5 text-tertiary opacity-0 group-hover:opacity-100 hover:bg-danger-subtle hover:text-danger-primary focus-visible:opacity-100"
                  >
                    <Archive className="size-4" />
                  </button>
                </div>
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
                <div className="flex items-center gap-2">
                  <Button type="button" variant="error-outline" onClick={() => setCaseArchiveId(selected.id)}>
                    <Archive className="size-4" /> Archive
                  </Button>
                  <Button type="submit" variant="primary" disabled={saving}>
                    <Save className="size-4" /> {t("testing.cases.save_version")}
                  </Button>
                </div>
              </div>
              <label className="block text-12 font-medium text-secondary">
                {t("testing.cases.title_label")}
                <input
                  value={draft.title}
                  onChange={(event) => setDraft({ ...draft, title: event.target.value })}
                  className="mt-1 h-10 w-full rounded border border-subtle bg-surface-1 px-3 text-14 text-primary outline-none"
                />
              </label>
              <label className="block text-12 font-medium text-secondary">
                Test objective and details
                <textarea
                  value={textValue(draft.description ?? {})}
                  onChange={(event) => setDraft({ ...draft, description: { text: event.target.value } })}
                  placeholder="Describe what this case validates and any QA guidance."
                  className="mt-1 min-h-24 w-full rounded border border-subtle bg-surface-1 p-3 text-13 text-primary outline-none"
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
                  {t("testing.cases.case_type")}
                  <select
                    value={draft.case_type ?? "functional"}
                    onChange={(event) => setDraft({ ...draft, case_type: event.target.value as TTestCaseType })}
                    className="mt-1 h-10 w-full rounded border border-subtle bg-surface-1 px-2 text-13 text-primary"
                  >
                    {(["functional", "performance", "security", "reliability", "compliance"] as const).map((item) => (
                      <option key={item} value={item}>
                        {t(`testing.cases.type.${item}`)}
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
                Tags <span className="font-normal text-tertiary">(comma separated)</span>
                <input
                  value={(draft.tags ?? []).join(", ")}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      tags: event.target.value
                        .split(",")
                        .map((tag) => tag.trim())
                        .filter(Boolean),
                    })
                  }
                  className="mt-1 h-10 w-full rounded border border-subtle bg-surface-1 px-3 text-13 text-primary outline-none"
                />
              </label>
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
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="flex items-center gap-1.5 text-12 font-medium text-secondary">
                      <Paperclip className="size-4" /> Attachments
                    </p>
                    <p className="mt-1 text-11 text-tertiary">Images, documents, spreadsheets, logs, and archives.</p>
                  </div>
                  <label className="flex h-8 cursor-pointer items-center gap-1 rounded border border-subtle px-2 text-11 text-secondary hover:bg-layer-1">
                    <Upload className="size-3.5" /> {uploading ? "Uploading…" : "Upload file"}
                    <input
                      type="file"
                      className="hidden"
                      disabled={uploading}
                      onChange={async (event) => {
                        const file = event.target.files?.[0];
                        event.target.value = "";
                        if (!file) return;
                        setUploading(true);
                        try {
                          await uploadAttachment(workspaceSlug, projectId, selected.id, file);
                          setToast({ type: TOAST_TYPE.SUCCESS, title: "Attachment uploaded", message: file.name });
                        } catch (error) {
                          setToast({
                            type: TOAST_TYPE.ERROR,
                            title: "Attachment could not be uploaded",
                            message: errorMessage(error, "Check the file type and size, then try again."),
                          });
                        } finally {
                          setUploading(false);
                        }
                      }}
                    />
                  </label>
                </div>
                {selectedAttachments.length ? (
                  <div className="mt-3 grid grid-cols-1 gap-2 xl:grid-cols-2">
                    {selectedAttachments.map((attachment) => (
                      <div key={attachment.id} className="group flex min-w-0 items-center gap-2 rounded bg-layer-1 p-2">
                        {attachment.preview_url ? (
                          <img
                            src={attachment.preview_url}
                            alt=""
                            className="size-10 shrink-0 rounded border border-subtle object-cover"
                          />
                        ) : attachment.attributes.type.startsWith("image/") ? (
                          <ImageIcon className="size-5 shrink-0 text-tertiary" />
                        ) : (
                          <FileText className="size-5 shrink-0 text-tertiary" />
                        )}
                        <a
                          href={attachment.download_url}
                          className="min-w-0 flex-1 truncate text-11 font-medium text-primary hover:underline"
                        >
                          {attachment.attributes.name}
                        </a>
                        <button
                          type="button"
                          aria-label={`Delete attachment ${attachment.attributes.name}`}
                          onClick={() =>
                            void deleteAttachment(workspaceSlug, projectId, selected.id, attachment.id).catch((error) =>
                              setToast({
                                type: TOAST_TYPE.ERROR,
                                title: "Attachment could not be deleted",
                                message: errorMessage(error, "Please try again."),
                              })
                            )
                          }
                          className="rounded p-1 text-tertiary opacity-0 group-hover:opacity-100 hover:bg-danger-subtle hover:text-danger-primary focus:opacity-100"
                        >
                          <Trash2 className="size-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-3 text-11 text-tertiary">No attachments yet.</p>
                )}
              </div>
              <TestCaseTraceability
                testCase={selected}
                workspaceSlug={workspaceSlug}
                projectId={projectId}
                onLinkRequirement={() => setLinking(true)}
                onUnlinkWorkItem={(workItemId) =>
                  void unlinkWorkItem(workspaceSlug, projectId, selected.id, workItemId)
                }
              />
              {draft.case_type !== "functional" && draft.case_type !== undefined && (
                <div className="rounded border border-subtle p-3">
                  <p className="text-12 font-medium text-secondary">{t("testing.cases.threshold")}</p>
                  {(() => {
                    // The expectation is already structured on the step; rendering it as a
                    // threshold rather than prose is what makes it judgeable and chartable.
                    const expectation = (selected.current.steps[0]?.expected_result ?? {}) as TTestThreshold;
                    const latest = selected.executions[0];
                    if (expectation.threshold === undefined)
                      return <p className="mt-1 text-11 text-tertiary">{t("testing.cases.threshold_hint")}</p>;
                    return (
                      <div className="mt-2 flex flex-wrap items-center gap-4 text-12">
                        <span className="font-mono text-primary">
                          {expectation.metric} {expectation.operator} {expectation.threshold} {expectation.unit}
                        </span>
                        <span className="text-tertiary">
                          {t("testing.cases.measured")}:{" "}
                          {latest ? t(`testing.status.${latest.latest_status}`) : t("testing.cases.no_measurement")}
                        </span>
                      </div>
                    );
                  })()}
                </div>
              )}
              <TestCaseExecutionHistory testCase={selected} workspaceSlug={workspaceSlug} projectId={projectId} />
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
            openWorkItemsInNewTab={false}
            handleOnSubmit={async (items) => {
              await Promise.all(items.map((item) => linkWorkItem(workspaceSlug, projectId, selected.id, item.id)));
              setLinking(false);
            }}
          />
        )}
      </section>
      <AlertModalCore
        handleClose={() => setCaseArchiveId(undefined)}
        handleSubmit={() => void handleArchiveCase()}
        isSubmitting={archivingCase}
        isOpen={!!caseToArchive}
        title="Archive test case"
        primaryButtonText={{ default: "Archive", loading: "Archiving" }}
        content={
          <>
            Archive <span className="font-medium text-primary">TC-{caseToArchive?.sequence}</span>? It will disappear
            from the active library, while pinned run versions and historical results remain available.
          </>
        }
      />
    </>
  );
});
