/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { orderBy } from "lodash-es";
import { Download, Folder, FolderPlus, FlaskConical, Link2, Plus, Save, Upload } from "lucide-react";
import { observer } from "mobx-react";
import { Button } from "@plane/propel/button";
import type { TTestCase, TTestCaseInput } from "@plane/types";
import { useTesting } from "@/hooks/store/use-testing";

type Props = { workspaceSlug: string; projectId: string };

const textValue = (value: Record<string, unknown>) =>
  typeof value.text === "string" ? value.text : Object.keys(value).length ? JSON.stringify(value) : "";

export const TestLibraryView = observer(function TestLibraryView({ workspaceSlug, projectId }: Props) {
  const {
    cases,
    folders,
    loading,
    createCase,
    updateCase,
    createFolder,
    linkWorkItem,
    exportLibraryCSV,
    importLibraryCSV,
  } = useTesting();
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string>();
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [title, setTitle] = useState("");
  const [folderName, setFolderName] = useState("");
  const [issueId, setIssueId] = useState("");
  const [draft, setDraft] = useState<TTestCaseInput>();
  const testFolders = orderBy(Object.values(folders), ["sort_order", "name"], ["asc", "asc"]);
  const testCases = orderBy(
    Object.values(cases).filter((item) => !selectedFolder || item.folder_id === selectedFolder),
    ["sequence"],
    ["asc"]
  );
  const selected = selectedId ? cases[selectedId] : undefined;

  const beginEdit = (testCase: TTestCase) => {
    setSelectedId(testCase.id);
    setIssueId("");
    setDraft({
      title: testCase.current.title,
      folder_id: testCase.folder_id,
      description: testCase.current.description,
      preconditions: testCase.current.preconditions,
      priority: testCase.current.priority,
      tags: testCase.current.tags,
      steps: testCase.current.steps.map((step) => ({ action: step.action, expected_result: step.expected_result })),
    });
  };

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
      beginEdit(created);
    } finally {
      setSaving(false);
    }
  };

  if (loading)
    return <div className="flex flex-1 items-center justify-center text-13 text-secondary">Loading test library…</div>;

  return (
    <section className="flex min-h-0 flex-1 overflow-hidden rounded-lg border border-subtle bg-surface-1">
      <aside className="w-56 shrink-0 overflow-y-auto border-r border-subtle bg-surface-2 p-3">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-11 font-semibold text-secondary uppercase">Folders</span>
          <FolderPlus className="size-4 text-tertiary" />
        </div>
        <button
          type="button"
          onClick={() => setSelectedFolder(null)}
          className={`flex w-full items-center gap-2 rounded px-2 py-2 text-12 ${!selectedFolder ? "bg-layer-2 text-primary" : "text-secondary hover:bg-layer-1"}`}
        >
          <FlaskConical className="size-4" /> All test cases
        </button>
        {testFolders.map((item) => (
          <button
            type="button"
            key={item.id}
            onClick={() => setSelectedFolder(item.id)}
            className={`flex w-full items-center gap-2 rounded px-2 py-2 text-12 ${selectedFolder === item.id ? "bg-layer-2 text-primary" : "text-secondary hover:bg-layer-1"}`}
          >
            <Folder className="size-4" /> {item.name}
          </button>
        ))}
        <form
          className="mt-3 flex gap-1"
          onSubmit={async (event) => {
            event.preventDefault();
            if (!folderName.trim()) return;
            await createFolder(workspaceSlug, projectId, folderName.trim(), selectedFolder);
            setFolderName("");
          }}
        >
          <input
            value={folderName}
            onChange={(event) => setFolderName(event.target.value)}
            placeholder="New folder"
            className="h-8 min-w-0 flex-1 rounded border border-subtle bg-surface-1 px-2 text-12 text-primary outline-none"
          />
          <Button type="submit" variant="secondary" disabled={!folderName.trim()}>
            +
          </Button>
        </form>
      </aside>

      <div className="w-80 shrink-0 overflow-y-auto border-r border-subtle">
        <div className="flex items-center justify-between border-b border-subtle p-3">
          <div>
            <h1 className="text-14 font-semibold text-primary">Test cases</h1>
            <p className="text-11 text-secondary">{testCases.length} cases</p>
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
              aria-label="Export test library as CSV"
            >
              <Download className="size-4" />
            </Button>
            <label
              className="flex h-8 cursor-pointer items-center rounded border border-subtle px-2 text-secondary hover:bg-layer-1"
              aria-label="Import test library CSV"
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
              <Plus className="size-4" /> Add
            </Button>
          </div>
        </div>
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
              placeholder="Test case title"
              className="h-9 w-full rounded border border-subtle bg-surface-1 px-2 text-13 text-primary outline-none"
            />
            <div className="mt-2 flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" disabled={!title.trim() || saving}>
                Create
              </Button>
            </div>
          </form>
        )}
        {testCases.map((testCase) => (
          <button
            type="button"
            key={testCase.id}
            onClick={() => beginEdit(testCase)}
            className={`w-full border-b border-subtle p-3 text-left ${selectedId === testCase.id ? "bg-layer-1" : "hover:bg-surface-2"}`}
          >
            <span className="text-10 font-medium text-tertiary">
              TC-{testCase.sequence} · v{testCase.current_version}
            </span>
            <span className="mt-1 block text-13 font-medium text-primary">{testCase.current.title}</span>
            <span className="mt-1 block text-11 text-secondary capitalize">{testCase.current.priority}</span>
          </button>
        ))}
      </div>

      <div className="min-w-0 flex-1 overflow-y-auto p-5">
        {!selected || !draft ? (
          <div className="flex h-full items-center justify-center text-13 text-secondary">
            Select a case to inspect or edit it.
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
                  TC-{selected.sequence} · editing creates v{selected.current_version + 1}
                </span>
                <h2 className="mt-1 text-18 font-semibold text-primary">Case detail</h2>
              </div>
              <Button type="submit" variant="primary" disabled={saving}>
                <Save className="size-4" /> Save new version
              </Button>
            </div>
            <label className="block text-12 font-medium text-secondary">
              Title
              <input
                value={draft.title}
                onChange={(event) => setDraft({ ...draft, title: event.target.value })}
                className="mt-1 h-10 w-full rounded border border-subtle bg-surface-1 px-3 text-14 text-primary outline-none"
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-12 font-medium text-secondary">
                Folder
                <select
                  value={draft.folder_id ?? ""}
                  onChange={(event) => setDraft({ ...draft, folder_id: event.target.value || null })}
                  className="mt-1 h-10 w-full rounded border border-subtle bg-surface-1 px-2 text-13 text-primary"
                >
                  <option value="">Unfiled</option>
                  {testFolders.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-12 font-medium text-secondary">
                Priority
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
              Preconditions
              <textarea
                value={textValue(draft.preconditions ?? {})}
                onChange={(event) => setDraft({ ...draft, preconditions: { text: event.target.value } })}
                className="mt-1 min-h-20 w-full rounded border border-subtle bg-surface-1 p-3 text-13 text-primary outline-none"
              />
            </label>
            <label className="block text-12 font-medium text-secondary">
              Steps <span className="font-normal text-tertiary">(one per line: action | expected)</span>
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
              <p className="text-12 font-medium text-secondary">Requirement links</p>
              <p className="mt-1 text-11 text-tertiary">
                {selected.work_item_ids.length
                  ? `${selected.work_item_ids.length} linked work item(s)`
                  : "No linked work items"}
              </p>
              <div className="mt-2 flex gap-2">
                <input
                  value={issueId}
                  onChange={(event) => setIssueId(event.target.value)}
                  placeholder="Plane work item UUID"
                  className="h-9 min-w-0 flex-1 rounded border border-subtle bg-surface-1 px-2 text-12 text-primary outline-none"
                />
                <Button
                  type="button"
                  variant="secondary"
                  disabled={!issueId.trim()}
                  onClick={async () => {
                    await linkWorkItem(workspaceSlug, projectId, selected.id, issueId.trim());
                    setIssueId("");
                  }}
                >
                  <Link2 className="size-4" /> Link
                </Button>
              </div>
            </div>
          </form>
        )}
      </div>
    </section>
  );
});
