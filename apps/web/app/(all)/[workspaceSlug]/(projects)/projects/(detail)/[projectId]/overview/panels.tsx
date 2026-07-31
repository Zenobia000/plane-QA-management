/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { ExternalLink, Pencil, Trash2 } from "lucide-react";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TProjectActivityEvent, TProjectOverviewLink, TProjectMilestoneSummary } from "@plane/types";
import { readError } from "./errors";

// The column behind these is a plain URLField, so anything longer is rejected by the
// serializer rather than truncated. Checking here turns a silent 400 into a hint.
const URL_MAX_LENGTH = 200;
const TITLE_MAX_LENGTH = 255;

/** Rejects what the serializer would reject anyway, before a round trip. */
function validateLink(url: string, title: string): string | null {
  if (url.length > URL_MAX_LENGTH) return `Keep the URL under ${URL_MAX_LENGTH} characters.`;
  if (title.length > TITLE_MAX_LENGTH) return `Keep the title under ${TITLE_MAX_LENGTH} characters.`;
  // The serializer prepends a scheme when one is missing, so "example.com/doc" is fine.
  // What it cannot accept is a bare word with no host at all.
  if (!/^(https?:\/\/)?[^\s/]+\.[^\s/]+/i.test(url)) return "Enter a URL, for example https://example.com.";
  return null;
}

export function LinksPanel({
  links,
  disabled,
  onAdd,
  onRemove,
}: {
  links: TProjectOverviewLink[];
  disabled: boolean;
  onAdd: (url: string, title: string) => Promise<void>;
  onRemove: (linkId: string) => Promise<void>;
}) {
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [invalid, setInvalid] = useState<string | null>(null);

  const add = async () => {
    const trimmedUrl = url.trim();
    const trimmedTitle = title.trim();
    if (!trimmedUrl) return;

    const problem = validateLink(trimmedUrl, trimmedTitle);
    if (problem) {
      setInvalid(problem);
      return;
    }

    setInvalid(null);
    setBusy(true);
    try {
      await onAdd(trimmedUrl, trimmedTitle);
      setUrl("");
      setTitle("");
    } catch (error) {
      // Without this the rejection was unhandled: the inputs kept their text and the
      // button re-enabled, which reads as the button doing nothing at all.
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Link not added",
        message: readError(error, "The link could not be saved."),
      });
    } finally {
      setBusy(false);
    }
  };

  const remove = async (linkId: string) => {
    try {
      await onRemove(linkId);
    } catch (error) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Link not removed",
        message: readError(error, "The link could not be removed."),
      });
    }
  };

  return (
    <section className="rounded border border-subtle p-4">
      <h2 className="text-13 font-medium text-primary">Links</h2>
      <ul className="mt-2 space-y-1.5">
        {links.map((link) => (
          <li key={link.id} className="flex items-center gap-2">
            <a
              href={link.url}
              target="_blank"
              rel="noreferrer"
              className="flex min-w-0 flex-1 items-center gap-1.5 text-12 text-accent-primary hover:underline"
            >
              <ExternalLink className="size-3.5 shrink-0" />
              <span className="truncate">{link.title || link.url}</span>
            </a>
            {!disabled && (
              <button
                type="button"
                aria-label={`Remove ${link.title || link.url}`}
                className="text-tertiary hover:text-danger-primary"
                onClick={() => void remove(link.id)}
              >
                <Trash2 className="size-3.5" />
              </button>
            )}
          </li>
        ))}
        {!links.length && <li className="text-12 text-tertiary">No links yet.</li>}
      </ul>

      {!disabled && (
        <div className="mt-3">
          <div className="flex gap-2">
            <input
              aria-label="Link title"
              className="h-8 w-28 rounded border border-subtle bg-surface-1 px-2 text-12 outline-none focus:border-accent-strong"
              placeholder="Title"
              value={title}
              onChange={(event) => {
                setTitle(event.target.value);
                setInvalid(null);
              }}
            />
            <input
              aria-label="Link URL"
              aria-invalid={!!invalid}
              className={`h-8 flex-1 rounded border bg-surface-1 px-2 text-12 outline-none ${
                invalid ? "border-danger-strong" : "border-subtle focus:border-accent-strong"
              }`}
              placeholder="https://"
              value={url}
              onChange={(event) => {
                setUrl(event.target.value);
                setInvalid(null);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter") void add();
              }}
            />
            <button
              type="button"
              className="h-8 rounded bg-surface-2 px-3 text-12 font-medium text-primary disabled:opacity-50"
              disabled={busy || !url.trim()}
              onClick={() => void add()}
            >
              Add
            </button>
          </div>
          {invalid && <p className="mt-1.5 text-11 text-danger-primary">{invalid}</p>}
        </div>
      )}
    </section>
  );
}

/**
 * Milestones, with how much of each is done -- and the controls to change them.
 *
 * Counts rather than names alone: a milestone list without them is decoration, and the
 * reason to put one on this page is to see what is left.
 *
 * Managed here rather than behind a settings page because this is where a reader meets
 * them. They were display-only until the app API grew write routes, so a seeded project
 * showed milestones nobody could rename, redate or remove without an API key.
 */
export function MilestonesPanel({
  milestones,
  disabled,
  onCreate,
  onRename,
  onRemove,
}: {
  milestones: TProjectMilestoneSummary[];
  disabled: boolean;
  onCreate: (name: string, targetDate: string | null) => Promise<void>;
  onRename: (milestoneId: string, name: string, targetDate: string | null) => Promise<void>;
  onRemove: (milestoneId: string) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDate, setEditDate] = useState("");

  const report = (error: unknown, title: string, fallback: string) =>
    setToast({ type: TOAST_TYPE.ERROR, title, message: readError(error, fallback) });

  const create = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setBusy(true);
    try {
      await onCreate(trimmed, targetDate || null);
      setName("");
      setTargetDate("");
    } catch (error) {
      report(error, "Milestone not created", "The milestone could not be created.");
    } finally {
      setBusy(false);
    }
  };

  const startEditing = (milestone: TProjectMilestoneSummary) => {
    setEditing(milestone.id);
    setEditName(milestone.name);
    setEditDate(milestone.target_date ?? "");
  };

  const commitEdit = async () => {
    const trimmed = editName.trim();
    if (!editing || !trimmed) return;
    try {
      await onRename(editing, trimmed, editDate || null);
      setEditing(null);
    } catch (error) {
      report(error, "Milestone not saved", "The change could not be saved.");
    }
  };

  const remove = async (milestone: TProjectMilestoneSummary) => {
    try {
      await onRemove(milestone.id);
    } catch (error) {
      report(error, "Milestone not removed", "The milestone could not be removed.");
    }
  };

  return (
    <section className="rounded border border-subtle p-4">
      <h2 className="text-13 font-medium text-primary">Milestones</h2>
      <ul className="mt-2 space-y-2">
        {milestones.map((milestone) => (
          <li key={milestone.id} className="group">
            {editing === milestone.id ? (
              <div className="flex gap-2">
                <input
                  aria-label="Milestone name"
                  className="h-8 min-w-0 flex-1 rounded border border-subtle bg-surface-1 px-2 text-12 outline-none focus:border-accent-strong"
                  value={editName}
                  onChange={(event) => setEditName(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") void commitEdit();
                    if (event.key === "Escape") setEditing(null);
                  }}
                />
                <input
                  type="date"
                  aria-label="Milestone target date"
                  className="h-8 w-32 rounded border border-subtle bg-surface-1 px-2 text-12 outline-none focus:border-accent-strong"
                  value={editDate}
                  onChange={(event) => setEditDate(event.target.value)}
                />
                <button
                  type="button"
                  className="h-8 rounded bg-surface-2 px-2 text-12 font-medium text-primary"
                  onClick={() => void commitEdit()}
                >
                  Save
                </button>
              </div>
            ) : (
              <div className="flex items-baseline justify-between gap-2">
                <span className="truncate text-12 text-primary">{milestone.name}</span>
                <span className="flex shrink-0 items-center gap-1.5 text-11 text-tertiary">
                  {milestone.completed}/{milestone.total}
                  {milestone.target_date ? ` · ${milestone.target_date}` : ""}
                  {!disabled && (
                    <>
                      <button
                        type="button"
                        aria-label={`Edit ${milestone.name}`}
                        className="opacity-0 transition-opacity group-hover:opacity-100 hover:text-primary"
                        onClick={() => startEditing(milestone)}
                      >
                        <Pencil className="size-3" />
                      </button>
                      {/* The server refuses to delete a milestone that still carries work
                          items, so the control is not offered when it would only fail. */}
                      {milestone.total === 0 && (
                        <button
                          type="button"
                          aria-label={`Remove ${milestone.name}`}
                          className="opacity-0 transition-opacity group-hover:opacity-100 hover:text-danger-primary"
                          onClick={() => void remove(milestone)}
                        >
                          <Trash2 className="size-3" />
                        </button>
                      )}
                    </>
                  )}
                </span>
              </div>
            )}
            <div className="mt-1 h-1 overflow-hidden rounded bg-surface-2">
              <div
                className="bg-accent-solid h-full"
                style={{
                  width: milestone.total ? `${(milestone.completed / milestone.total) * 100}%` : "0%",
                }}
              />
            </div>
          </li>
        ))}
        {/* Rendering nothing at all when the list was empty is why milestones read as
            appearing from nowhere: there was no sign the feature existed until data did. */}
        {!milestones.length && (
          <li className="text-12 text-tertiary">No milestones yet. Add one to track a commitment.</li>
        )}
      </ul>

      {!disabled && (
        <div className="mt-3 flex gap-2">
          <input
            aria-label="New milestone name"
            className="h-8 min-w-0 flex-1 rounded border border-subtle bg-surface-1 px-2 text-12 outline-none focus:border-accent-strong"
            placeholder="Milestone name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void create();
            }}
          />
          <input
            type="date"
            aria-label="New milestone target date"
            className="h-8 w-32 rounded border border-subtle bg-surface-1 px-2 text-12 outline-none focus:border-accent-strong"
            value={targetDate}
            onChange={(event) => setTargetDate(event.target.value)}
          />
          <button
            type="button"
            className="h-8 rounded bg-surface-2 px-3 text-12 font-medium text-primary disabled:opacity-50"
            disabled={busy || !name.trim()}
            onClick={() => void create()}
          >
            Add
          </button>
        </div>
      )}
    </section>
  );
}

/** "backlog" -> "In progress" reads better than the raw column value. */
function readValue(value: string | null): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}

export function ActivityPanel({
  activities,
  hasMore,
  loadingMore,
  onLoadMore,
}: {
  activities: TProjectActivityEvent[];
  hasMore: boolean;
  loadingMore: boolean;
  onLoadMore: () => void;
}) {
  return (
    <section className="rounded border border-subtle p-4">
      <h2 className="text-13 font-medium text-primary">Activity</h2>
      {/* The feed is unbounded by nature -- a row per field change per work item -- so it
          scrolls inside the panel instead of stretching the page to whatever the server
          last returned. */}
      <ul className="mt-2 max-h-96 space-y-2 overflow-y-auto pr-1">
        {activities.map((activity) => {
          const from = readValue(activity.old_value);
          const to = readValue(activity.new_value);
          return (
            <li key={activity.id} className="text-12 text-secondary">
              <span className="text-primary">{activity.actor?.display_name ?? "Someone"}</span> {activity.verb}{" "}
              {activity.field ?? ""}
              {activity.work_item && <span className="text-tertiary"> on {activity.work_item.name}</span>}
              <time className="ml-1 text-11 text-tertiary" dateTime={activity.created_at}>
                {new Date(activity.created_at).toLocaleDateString()}
              </time>
              {/* The endpoint has always sent these; nothing rendered them, so every row
                  read as "someone changed something" with no before or after. */}
              {(from || to) && (
                <span className="ml-1 text-11 text-tertiary">
                  {from && <span className="line-through">{from}</span>}
                  {from && to && " → "}
                  {to && <span className="text-secondary">{to}</span>}
                </span>
              )}
            </li>
          );
        })}
        {!activities.length && <li className="text-12 text-tertiary">Nothing has happened yet.</li>}
      </ul>
      {hasMore && (
        <button
          type="button"
          className="mt-2 text-12 font-medium text-accent-primary hover:underline disabled:opacity-50"
          disabled={loadingMore}
          onClick={onLoadMore}
        >
          {loadingMore ? "Loading…" : "Load more"}
        </button>
      )}
    </section>
  );
}
