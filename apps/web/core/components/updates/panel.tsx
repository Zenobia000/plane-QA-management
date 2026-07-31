/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { useTranslation } from "@plane/i18n";
import type { TEntityUpdate, TUpdateEntityName, TUpdateStatus } from "@plane/types";

export const UPDATE_STATUS_LABELS: Record<TUpdateStatus, string> = {
  on_track: "On track",
  at_risk: "At risk",
  off_track: "Off track",
};

const STATUS_CLASSES: Record<TUpdateStatus, string> = {
  on_track: "bg-success-subtle text-success-primary",
  at_risk: "bg-warning-subtle text-warning-primary",
  off_track: "bg-danger-subtle text-danger-primary",
};

export function UpdateStatusPill({ status }: { status: TUpdateStatus }) {
  return (
    <span className={`rounded px-1.5 py-0.5 text-10 font-medium ${STATUS_CLASSES[status]}`}>
      {UPDATE_STATUS_LABELS[status]}
    </span>
  );
}

type Props = {
  entityName: TUpdateEntityName;
  updates: TEntityUpdate[];
  disabled?: boolean;
  onPost: (status: TUpdateStatus, description: string) => Promise<void>;
  /** Omit to render the thread without replies -- a peek view has no room for them. */
  onLoadReplies?: (updateId: string) => Promise<TEntityUpdate[]>;
  onReply?: (parentId: string, description: string) => Promise<void>;
  /**
   * How many updates the thread holds, when the caller is only passing the newest few.
   * Omit when `updates` is already the whole thread.
   */
  total?: number;
  /** Fetches the rest. Required for the "show all" control to appear. */
  onLoadAll?: () => Promise<TEntityUpdate[]>;
};

/**
 * One update and, on demand, the replies under it.
 *
 * Replies are fetched when the thread is opened rather than shipped with the list. The
 * overview shows ten updates and almost none of them are ever expanded, so eagerly loading
 * every reply would pay for a conversation nobody asked to read. `reply_count` comes down
 * with the update, which is enough to decide whether the control is worth showing.
 */
function UpdateThread({
  update,
  disabled,
  onLoadReplies,
  onReply,
}: {
  update: TEntityUpdate;
  disabled: boolean;
  onLoadReplies?: (updateId: string) => Promise<TEntityUpdate[]>;
  onReply?: (parentId: string, description: string) => Promise<void>;
}) {
  const [replies, setReplies] = useState<TEntityUpdate[] | null>(null);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);

  const canThread = Boolean(onLoadReplies && onReply);

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next && replies === null && onLoadReplies) setReplies(await onLoadReplies(update.id));
  };

  const send = async () => {
    if (!draft.trim() || !onReply || !onLoadReplies) return;
    setBusy(true);
    try {
      await onReply(update.id, draft.trim());
      setDraft("");
      setReplies(await onLoadReplies(update.id));
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="border-t border-subtle pt-3 first:border-t-0 first:pt-0">
      <div className="flex items-center gap-2">
        <UpdateStatusPill status={update.status} />
        <span className="text-11 text-secondary">{update.actor_detail?.display_name ?? "Someone"}</span>
        <time className="text-11 text-tertiary" dateTime={update.created_at}>
          {new Date(update.created_at).toLocaleDateString()}
        </time>
      </div>
      {update.description && <p className="mt-1 text-12 text-primary">{update.description}</p>}

      {canThread && (
        <>
          <button
            type="button"
            className="mt-1 text-11 text-tertiary hover:text-secondary"
            onClick={() => void toggle()}
          >
            {open ? "Hide replies" : update.reply_count ? `${update.reply_count} replies` : "Reply"}
          </button>

          {open && (
            <div className="mt-2 space-y-2 border-l border-subtle pl-3">
              {(replies ?? []).map((reply) => (
                <div key={reply.id}>
                  <div className="flex items-center gap-2">
                    <span className="text-11 text-secondary">{reply.actor_detail?.display_name ?? "Someone"}</span>
                    <time className="text-11 text-tertiary" dateTime={reply.created_at}>
                      {new Date(reply.created_at).toLocaleDateString()}
                    </time>
                  </div>
                  <p className="text-12 text-primary">{reply.description}</p>
                </div>
              ))}
              {replies !== null && !replies.length && <p className="text-11 text-tertiary">No replies yet.</p>}

              {!disabled && (
                <div className="flex gap-2">
                  <input
                    aria-label="Reply to this update"
                    className="h-7 flex-1 rounded border border-subtle bg-surface-1 px-2 text-12 text-primary outline-none focus:border-accent-strong"
                    placeholder="Reply"
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                  />
                  <button
                    type="button"
                    className="h-7 rounded bg-surface-2 px-2 text-11 font-medium text-primary disabled:opacity-50"
                    disabled={busy || !draft.trim()}
                    onClick={() => void send()}
                  >
                    Send
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </li>
  );
}

/**
 * The status thread, for whichever entity is being reported on.
 *
 * One component for projects and work items because it is one model. The official product
 * shipped updates on epics first and then extended them everywhere, which is the same
 * conclusion arrived at from the other direction.
 */
export function UpdatesPanel({
  entityName,
  updates,
  disabled = false,
  onPost,
  onLoadReplies,
  onReply,
  total,
  onLoadAll,
}: Props) {
  const [status, setStatus] = useState<TUpdateStatus>("on_track");
  const [description, setDescription] = useState("");
  const [posting, setPosting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The full thread, once asked for. Null until then, so `updates` stays the source of
  // truth for the common case and a refetch after posting is not fighting a stale copy.
  const [expanded, setExpanded] = useState<TEntityUpdate[] | null>(null);
  const [expanding, setExpanding] = useState(false);
  const { t } = useTranslation();

  const shown = expanded ?? updates;
  const hidden = (total ?? shown.length) - shown.length;

  const showAll = async () => {
    if (!onLoadAll) return;
    setExpanding(true);
    setError(null);
    try {
      setExpanded(await onLoadAll());
    } catch {
      setError(t("project_overview.updates.load_error"));
    } finally {
      setExpanding(false);
    }
  };

  const submit = async () => {
    setPosting(true);
    setError(null);
    try {
      await onPost(status, description.trim());
      setDescription("");
    } catch {
      setError("Could not post the update.");
    } finally {
      setPosting(false);
    }
  };

  return (
    <section className="rounded border border-subtle p-4">
      <h2 className="text-13 font-medium text-primary">Updates</h2>
      <p className="mt-0.5 text-11 text-tertiary">
        {entityName === "project"
          ? "Where this project stands, so the answer is not a meeting."
          : "Where this work item stands."}
      </p>

      {!disabled && (
        <div className="mt-3 space-y-2">
          <div className="flex gap-2">
            {(Object.keys(UPDATE_STATUS_LABELS) as TUpdateStatus[]).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setStatus(value)}
                className={`rounded px-2 py-1 text-11 font-medium ${
                  status === value ? STATUS_CLASSES[value] : "bg-surface-2 text-tertiary"
                }`}
              >
                {UPDATE_STATUS_LABELS[value]}
              </button>
            ))}
          </div>
          <textarea
            aria-label="Update description"
            className="min-h-16 w-full rounded border border-subtle bg-surface-1 px-2 py-1.5 text-12 text-primary outline-none focus:border-accent-strong"
            placeholder="What changed, and what it means for the date."
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="bg-accent-solid h-8 rounded px-3 text-12 font-medium text-inverse disabled:opacity-50"
              disabled={posting}
              onClick={() => void submit()}
            >
              {posting ? "Posting…" : "Post update"}
            </button>
            {error && <p className="text-11 text-danger-primary">{error}</p>}
          </div>
        </div>
      )}

      <ul className="mt-4 space-y-3">
        {shown.map((update) => (
          <UpdateThread
            key={update.id}
            update={update}
            disabled={disabled}
            onLoadReplies={onLoadReplies}
            onReply={onReply}
          />
        ))}
        {!shown.length && <li className="text-12 text-tertiary">No updates yet.</li>}
      </ul>
      {/* The caller embeds only the newest few. Saying how many are hidden beats
          truncating silently, which reads as the thread having stopped. */}
      {hidden > 0 && onLoadAll && (
        <button
          type="button"
          className="mt-3 text-12 font-medium text-accent-primary hover:underline disabled:opacity-50"
          disabled={expanding}
          onClick={() => void showAll()}
        >
          {expanding
            ? t("project_overview.activity.loading")
            : t("project_overview.updates.show_earlier", { count: hidden })}
        </button>
      )}
    </section>
  );
}
