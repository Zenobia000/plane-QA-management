/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef, useState } from "react";
import { Bold, Code2, Eye, FileText, Link2, List, ListOrdered, Paperclip, Pencil, UploadCloud, X } from "lucide-react";
import remarkGfm from "remark-gfm";
import { MAX_FILE_SIZE } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { MarkdownRenderer } from "@/components/ui/markdown-to-component";

export type TResultEvidenceDraftFile = {
  id: string;
  file: File;
  status: "pending" | "uploading" | "failed";
  error?: string;
};

type Props = {
  value: string;
  files: TResultEvidenceDraftFile[];
  disabled?: boolean;
  readOnly?: boolean;
  error?: string;
  onChange: (value: string) => void;
  onFilesChange: (files: TResultEvidenceDraftFile[]) => void;
};

const fileIdentity = (file: File) => `${file.name}:${file.size}:${file.lastModified}`;

const createDraftFile = (file: File): TResultEvidenceDraftFile => ({
  id: globalThis.crypto?.randomUUID?.() ?? `${fileIdentity(file)}:${Math.random().toString(36).slice(2)}`,
  file,
  status: "pending",
});

const formatBytes = (size: number) => {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
};

function DraftImagePreview({ file }: { file: File }) {
  const [source, setSource] = useState<string>();

  useEffect(() => {
    if (!file.type.startsWith("image/") || typeof URL.createObjectURL !== "function") return undefined;
    const objectUrl = URL.createObjectURL(file);
    setSource(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  if (!source) {
    return (
      <span className="flex size-10 shrink-0 items-center justify-center rounded bg-layer-2 text-tertiary">
        <FileText className="size-4" />
      </span>
    );
  }

  return <img src={source} alt="" className="size-10 shrink-0 rounded object-cover" />;
}

export function EvidenceComposer({
  value,
  files,
  disabled = false,
  readOnly = false,
  error,
  onChange,
  onFilesChange,
}: Props) {
  const { t } = useTranslation();
  const maxFileSize = MAX_FILE_SIZE;
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [mode, setMode] = useState<"write" | "preview">("write");
  const [dragActive, setDragActive] = useState(false);
  const [validationError, setValidationError] = useState<string>();

  const addFiles = (incoming: File[]) => {
    if (disabled || !incoming.length) return;
    const existing = new Set(files.map(({ file }) => fileIdentity(file)));
    const accepted: TResultEvidenceDraftFile[] = [];
    const rejected: File[] = [];

    incoming.forEach((file) => {
      if (file.size > maxFileSize) {
        rejected.push(file);
        return;
      }
      const identity = fileIdentity(file);
      if (existing.has(identity)) return;
      existing.add(identity);
      accepted.push(createDraftFile(file));
    });

    if (accepted.length) onFilesChange([...files, ...accepted]);
    setValidationError(
      rejected.length
        ? t("testing.execution.file_too_large", {
            count: rejected.length,
            size: Math.round(maxFileSize / (1024 * 1024)),
          })
        : undefined
    );
  };

  const replaceSelection = (before: string, after: string, placeholder: string) => {
    const textarea = textareaRef.current;
    if (!textarea || readOnly || disabled) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = value.slice(start, end) || placeholder;
    const nextValue = `${value.slice(0, start)}${before}${selected}${after}${value.slice(end)}`;
    onChange(nextValue);
    requestAnimationFrame(() => {
      textarea.focus();
      textarea.setSelectionRange(start + before.length, start + before.length + selected.length);
    });
  };

  const prefixSelectedLines = (prefix: (index: number) => string) => {
    const textarea = textareaRef.current;
    if (!textarea || readOnly || disabled) return;
    const start = value.lastIndexOf("\n", Math.max(0, textarea.selectionStart - 1)) + 1;
    const selectionEnd = textarea.selectionEnd;
    const lineEnd = value.indexOf("\n", selectionEnd);
    const end = lineEnd === -1 ? value.length : lineEnd;
    const selected = value.slice(start, end) || t("testing.execution.list_item");
    const replacement = selected
      .split("\n")
      .map((line, index) => `${prefix(index)}${line}`)
      .join("\n");
    onChange(`${value.slice(0, start)}${replacement}${value.slice(end)}`);
    requestAnimationFrame(() => {
      textarea.focus();
      textarea.setSelectionRange(start, start + replacement.length);
    });
  };

  const toolbar = [
    {
      label: t("testing.execution.bold"),
      icon: Bold,
      action: () => replaceSelection("**", "**", t("testing.execution.bold_placeholder")),
    },
    {
      label: t("testing.execution.bullet_list"),
      icon: List,
      action: () => prefixSelectedLines(() => "- "),
    },
    {
      label: t("testing.execution.numbered_list"),
      icon: ListOrdered,
      action: () => prefixSelectedLines((index) => `${index + 1}. `),
    },
    {
      label: t("testing.execution.code"),
      icon: Code2,
      action: () => replaceSelection("`", "`", t("testing.execution.code_placeholder")),
    },
    {
      label: t("testing.execution.link"),
      icon: Link2,
      action: () => replaceSelection("[", "](https://)", t("testing.execution.link_placeholder")),
    },
  ];

  return (
    <section aria-labelledby="result-evidence-heading" className="rounded-lg border border-subtle bg-surface-1">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-subtle px-3 py-2">
        <div>
          <h4 id="result-evidence-heading" className="text-12 font-semibold text-secondary uppercase">
            {t("testing.execution.actual")}
          </h4>
          <p className="mt-0.5 text-11 text-tertiary">{t("testing.execution.markdown_hint")}</p>
        </div>
        <div
          className="flex rounded-md bg-layer-2 p-0.5"
          role="tablist"
          aria-label={t("testing.execution.editor_mode")}
        >
          <button
            type="button"
            role="tab"
            aria-selected={mode === "write"}
            onClick={() => setMode("write")}
            className={`flex items-center gap-1 rounded px-2 py-1 text-11 ${
              mode === "write" ? "shadow-sm bg-surface-1 text-primary" : "text-secondary"
            }`}
          >
            <Pencil className="size-3" /> {t("testing.execution.write")}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "preview"}
            onClick={() => setMode("preview")}
            className={`flex items-center gap-1 rounded px-2 py-1 text-11 ${
              mode === "preview" ? "shadow-sm bg-surface-1 text-primary" : "text-secondary"
            }`}
          >
            <Eye className="size-3" /> {t("testing.execution.preview")}
          </button>
        </div>
      </div>

      {mode === "write" ? (
        <>
          <div className="flex items-center gap-0.5 border-b border-subtle px-2 py-1.5">
            {toolbar.map(({ label, icon: Icon, action }) => (
              <button
                key={label}
                type="button"
                aria-label={label}
                title={label}
                disabled={disabled || readOnly}
                onMouseDown={(event) => event.preventDefault()}
                onClick={action}
                className="rounded p-1.5 text-secondary hover:bg-layer-2 hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
              >
                <Icon className="size-3.5" />
              </button>
            ))}
          </div>
          <textarea
            ref={textareaRef}
            data-evidence-editor
            value={value}
            readOnly={readOnly}
            disabled={disabled}
            onChange={(event) => onChange(event.target.value)}
            onPaste={(event) => {
              const pastedFiles = Array.from(event.clipboardData.files);
              if (!pastedFiles.length) return;
              event.preventDefault();
              addFiles(pastedFiles);
            }}
            onKeyDown={(event) => {
              if (event.key !== "Tab" || readOnly || disabled) return;
              event.preventDefault();
              replaceSelection("  ", "", "");
            }}
            className="font-mono min-h-36 w-full resize-y bg-transparent p-3 text-13 text-primary outline-none disabled:cursor-not-allowed disabled:opacity-60"
            placeholder={t("testing.execution.actual_placeholder")}
          />
        </>
      ) : (
        <div data-evidence-editor className="min-h-44 p-3">
          {value.trim() ? (
            <MarkdownRenderer markdown={value} options={{ remarkPlugins: [remarkGfm] }} />
          ) : (
            <p className="text-13 text-tertiary">{t("testing.execution.nothing_to_preview")}</p>
          )}
        </div>
      )}

      <label
        className={`m-3 flex cursor-pointer flex-col items-center justify-center rounded-md border border-dashed px-4 py-4 text-center transition-colors ${
          dragActive ? "border-accent-strong bg-accent-subtle" : "border-subtle bg-surface-2 hover:border-strong"
        } ${disabled ? "pointer-events-none opacity-50" : ""}`}
        onDragEnter={(event) => {
          event.preventDefault();
          setDragActive(true);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragActive(false);
        }}
        onDrop={(event) => {
          event.preventDefault();
          setDragActive(false);
          addFiles(Array.from(event.dataTransfer.files));
        }}
      >
        <UploadCloud className="size-5 text-tertiary" />
        <span className="mt-1 text-12 font-medium text-primary">{t("testing.execution.drop_files")}</span>
        <span className="mt-0.5 text-11 text-tertiary">
          {t("testing.execution.paste_files", { size: Math.round(maxFileSize / (1024 * 1024)) })}
        </span>
        <input
          type="file"
          multiple
          className="sr-only"
          disabled={disabled}
          onChange={(event) => {
            addFiles(Array.from(event.target.files ?? []));
            event.target.value = "";
          }}
        />
      </label>

      {files.length > 0 && (
        <ul className="mx-3 mb-3 grid gap-2 sm:grid-cols-2">
          {files.map((item) => (
            <li key={item.id} className="flex min-w-0 items-center gap-2 rounded-md border border-subtle p-2">
              <DraftImagePreview file={item.file} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-12 font-medium text-primary">{item.file.name}</span>
                <span className="flex items-center gap-1 text-10 text-tertiary">
                  {formatBytes(item.file.size)}
                  {item.status === "uploading" && <> · {t("testing.execution.uploading")}</>}
                  {item.status === "failed" && (
                    <span className="text-danger-primary"> · {t("testing.execution.upload_failed")}</span>
                  )}
                </span>
              </span>
              <button
                type="button"
                aria-label={t("testing.execution.remove", { name: item.file.name })}
                disabled={disabled || item.status === "uploading"}
                onClick={() => onFilesChange(files.filter((file) => file.id !== item.id))}
                className="rounded p-1 text-tertiary hover:bg-layer-2 hover:text-primary disabled:opacity-40"
              >
                <X className="size-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}

      {(validationError || error) && (
        <p role="alert" className="mx-3 mb-3 flex items-center gap-1 text-11 text-danger-primary">
          <Paperclip className="size-3.5" /> {validationError || error}
        </p>
      )}
    </section>
  );
}
