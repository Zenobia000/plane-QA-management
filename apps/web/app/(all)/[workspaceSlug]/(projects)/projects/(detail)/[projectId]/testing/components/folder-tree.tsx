/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { Check, FlaskConical, Folder, FolderPlus, Pencil, Trash2, X } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import type { TTestFolder } from "@plane/types";
import { AlertModalCore } from "@plane/ui";

type Props = {
  folders: TTestFolder[];
  selectedFolder: string | null;
  onSelect: (folderId: string | null) => void;
  onCreate: (name: string, parentId: string | null) => Promise<void>;
  onRename: (folderId: string, name: string) => Promise<void>;
  onDelete: (folderId: string) => Promise<void>;
};

const errorMessage = (error: unknown, fallback: string) => {
  if (typeof error === "string") return error;
  if (error instanceof Error) return error.message;
  if (error && typeof error === "object") {
    const { error: apiError, detail } = error as { error?: unknown; detail?: unknown };
    if (typeof apiError === "string") return apiError;
    if (typeof detail === "string") return detail;
  }
  return fallback;
};

/**
 * Flattens the suites into render order while keeping depth, so nesting shows up
 * in the sidebar. `TestFolder.parent` has always nested; only the rendering was
 * flat, which made a suite tree look like a pile of sibling folders.
 */
const inRenderOrder = (folders: TTestFolder[]) => {
  const byParent = new Map<string | null, TTestFolder[]>();
  for (const folder of folders) {
    const siblings = byParent.get(folder.parent_id) ?? [];
    siblings.push(folder);
    byParent.set(folder.parent_id, siblings);
  }
  const known = new Set(folders.map((folder) => folder.id));
  const ordered: Array<{ folder: TTestFolder; depth: number }> = [];
  const walk = (parentId: string | null, depth: number, seen: Set<string>) => {
    for (const folder of byParent.get(parentId) ?? []) {
      if (seen.has(folder.id)) continue;
      seen.add(folder.id);
      ordered.push({ folder, depth });
      walk(folder.id, depth + 1, seen);
    }
  };
  const seen = new Set<string>();
  walk(null, 0, seen);
  // A suite whose parent is missing from this page would otherwise vanish.
  for (const folder of folders) {
    if (!seen.has(folder.id) && (folder.parent_id === null || !known.has(folder.parent_id))) {
      seen.add(folder.id);
      ordered.push({ folder, depth: 0 });
      walk(folder.id, 1, seen);
    }
  }
  for (const folder of folders) {
    if (!seen.has(folder.id)) ordered.push({ folder, depth: 0 });
  }
  return ordered;
};

const iconButtonClass =
  "rounded p-1 text-tertiary opacity-0 hover:bg-layer-2 hover:text-primary group-hover:opacity-100 focus-visible:opacity-100";

export function FolderTree({ folders, selectedFolder, onSelect, onCreate, onRename, onDelete }: Props) {
  const { t } = useTranslation();
  const [folderName, setFolderName] = useState("");
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [pendingDelete, setPendingDelete] = useState<TTestFolder | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rows = inRenderOrder(folders);

  const beginRename = (folder: TTestFolder) => {
    setError(null);
    setRenamingId(folder.id);
    setRenameValue(folder.name);
  };

  const submitCreate = async () => {
    const name = folderName.trim();
    if (!name) return;
    setSubmitting(true);
    try {
      await onCreate(name, selectedFolder);
      setFolderName("");
      setError(null);
    } catch (createError) {
      setError(errorMessage(createError, t("testing.suites.create_failed")));
    } finally {
      setSubmitting(false);
    }
  };

  const submitRename = async (folderId: string) => {
    const name = renameValue.trim();
    if (!name) return;
    setSubmitting(true);
    try {
      await onRename(folderId, name);
      setRenamingId(null);
      setError(null);
    } catch (renameError) {
      setError(errorMessage(renameError, t("testing.suites.rename_failed")));
    } finally {
      setSubmitting(false);
    }
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setSubmitting(true);
    try {
      await onDelete(pendingDelete.id);
      setPendingDelete(null);
      setError(null);
    } catch (deleteError) {
      setError(errorMessage(deleteError, t("testing.suites.delete_conflict")));
      setPendingDelete(null);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <aside className="w-56 shrink-0 overflow-y-auto border-r border-subtle bg-surface-2 p-3">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-11 font-semibold text-secondary uppercase">{t("testing.suites.label")}</span>
        <FolderPlus className="size-4 text-tertiary" />
      </div>
      <button
        type="button"
        onClick={() => onSelect(null)}
        className={`flex w-full items-center gap-2 rounded px-2 py-2 text-12 ${!selectedFolder ? "bg-layer-2 text-primary" : "text-secondary hover:bg-layer-1"}`}
      >
        <FlaskConical className="size-4" /> {t("testing.suites.all_cases")}
      </button>
      {rows.map(({ folder, depth }) =>
        renamingId === folder.id ? (
          <form
            key={folder.id}
            className="mt-1 flex items-center gap-1"
            style={{ paddingLeft: depth * 12 }}
            onSubmit={(event) => {
              event.preventDefault();
              void submitRename(folder.id);
            }}
          >
            <input
              value={renameValue}
              onChange={(event) => setRenameValue(event.target.value)}
              aria-label={t("testing.suites.rename_label", { name: folder.name })}
              className="h-8 min-w-0 flex-1 rounded border border-subtle bg-surface-1 px-2 text-12 text-primary outline-none"
            />
            <button
              type="submit"
              aria-label={t("testing.suites.save", { name: folder.name })}
              disabled={submitting || !renameValue.trim()}
              className="rounded p-1 text-tertiary hover:bg-layer-2 hover:text-primary disabled:opacity-50"
            >
              <Check className="size-4" />
            </button>
            <button
              type="button"
              aria-label={t("testing.suites.cancel_rename", { name: folder.name })}
              onClick={() => setRenamingId(null)}
              className="rounded p-1 text-tertiary hover:bg-layer-2 hover:text-primary"
            >
              <X className="size-4" />
            </button>
          </form>
        ) : (
          <div key={folder.id} className="group flex items-center gap-1" style={{ paddingLeft: depth * 12 }}>
            <button
              type="button"
              onClick={() => onSelect(folder.id)}
              className={`flex min-w-0 flex-1 items-center gap-2 rounded px-2 py-2 text-12 ${selectedFolder === folder.id ? "bg-layer-2 text-primary" : "text-secondary hover:bg-layer-1"}`}
            >
              <Folder className="size-4 shrink-0" /> <span className="truncate">{folder.name}</span>
            </button>
            <button
              type="button"
              aria-label={t("testing.suites.rename", { name: folder.name })}
              onClick={() => beginRename(folder)}
              className={iconButtonClass}
            >
              <Pencil className="size-3.5" />
            </button>
            <button
              type="button"
              aria-label={t("testing.suites.delete", { name: folder.name })}
              onClick={() => {
                setError(null);
                setPendingDelete(folder);
              }}
              className={iconButtonClass}
            >
              <Trash2 className="size-3.5" />
            </button>
          </div>
        )
      )}
      {error && (
        <p role="alert" className="mt-2 text-11 text-danger-primary">
          {error}
        </p>
      )}
      <form
        className="mt-3 flex gap-1"
        onSubmit={(event) => {
          event.preventDefault();
          void submitCreate();
        }}
      >
        <input
          value={folderName}
          onChange={(event) => setFolderName(event.target.value)}
          placeholder={t("testing.suites.new_placeholder")}
          aria-label={t("testing.suites.new_name_label")}
          className="h-8 min-w-0 flex-1 rounded border border-subtle bg-surface-1 px-2 text-12 text-primary outline-none"
        />
        <Button type="submit" variant="secondary" disabled={!folderName.trim() || submitting}>
          +
        </Button>
      </form>
      {pendingDelete && (
        <AlertModalCore
          isOpen
          variant="danger"
          title={t("testing.suites.delete_title")}
          content={t("testing.suites.delete_content", { name: pendingDelete.name })}
          isSubmitting={submitting}
          handleClose={() => setPendingDelete(null)}
          handleSubmit={() => void confirmDelete()}
          primaryButtonText={{
            default: t("testing.suites.delete_confirm"),
            loading: t("testing.suites.delete_submitting"),
          }}
        />
      )}
    </aside>
  );
}
