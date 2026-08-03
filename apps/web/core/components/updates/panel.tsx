/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { Pencil, Trash2, X } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import type { IIssueLabel, TEntityUpdate, TUpdateEntityName, TUpdateStatus } from "@plane/types";

/** Translation keys rather than English, so the pill reads in the reader's language. */
export const UPDATE_STATUS_KEYS: Record<TUpdateStatus, string> = {
  on_track: "project_overview.updates.status.on_track",
  at_risk: "project_overview.updates.status.at_risk",
  off_track: "project_overview.updates.status.off_track",
};

const STATUS_CLASSES: Record<TUpdateStatus, string> = {
  on_track: "bg-success-subtle text-success-primary",
  at_risk: "bg-warning-subtle text-warning-primary",
  off_track: "bg-danger-subtle text-danger-primary",
};

export function UpdateStatusPill({ status }: { status: TUpdateStatus }) {
  const { t } = useTranslation();
  return (
    <span className={`rounded px-1.5 py-0.5 text-10 font-medium ${STATUS_CLASSES[status]}`}>
      {t(UPDATE_STATUS_KEYS[status])}
    </span>
  );
}

/**
 * A topic chip, coloured by whatever the team picked in project settings.
 *
 * The colour is inline rather than a class because it comes from the database -- there is
 * no Tailwind token for a hex someone chose ten seconds ago.
 */
function TopicChip({ label }: { label: IIssueLabel }) {
  const color = label.color || "#a3a3a3";
  return (
    <span
      className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-10 font-medium text-secondary"
      style={{ backgroundColor: `${color}1f` }}
    >
      <span className="size-1.5 rounded-full" style={{ backgroundColor: color }} />
      {label.name}
    </span>
  );
}

/** Toggle chips for filing an announcement under topics. */
function TopicPicker({
  labels,
  selected,
  onChange,
}: {
  labels: IIssueLabel[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {labels.map((label) => {
        const on = selected.includes(label.id);
        const color = label.color || "#a3a3a3";
        return (
          <button
            key={label.id}
            type="button"
            aria-pressed={on}
            onClick={() => onChange(on ? selected.filter((id) => id !== label.id) : [...selected, label.id])}
            className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-10 font-medium ${
              on ? "border-transparent text-secondary" : "border-subtle text-tertiary"
            }`}
            style={on ? { backgroundColor: `${color}1f` } : undefined}
          >
            <span className="size-1.5 rounded-full" style={{ backgroundColor: color }} />
            {label.name}
          </button>
        );
      })}
    </div>
  );
}

type Props = {
  entityName: TUpdateEntityName;
  updates: TEntityUpdate[];
  disabled?: boolean;
  onPost: (status: TUpdateStatus, description: string, labelIds: string[]) => Promise<void>;
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
  /**
   * The project's labels, doubling as the board's topics.
   *
   * Passing none switches the whole topic apparatus off -- no filter row, no picker, no
   * chips. That is the right shape for the work-item panel, which is one item's status
   * thread and has nothing to sort.
   */
  labels?: IIssueLabel[];
  /** Who is reading. Decides whose posts show an edit control. */
  currentUserId?: string;
  /** Admins moderate: a board nobody can clean up is its own problem. */
  canModerate?: boolean;
  onEdit?: (updateId: string, description: string, labelIds: string[]) => Promise<void>;
  onDelete?: (updateId: string) => Promise<void>;
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
  labels,
  canChange,
  onLoadReplies,
  onReply,
  onEdit,
  onDelete,
}: {
  update: TEntityUpdate;
  disabled: boolean;
  labels: IIssueLabel[];
  canChange: boolean;
  onLoadReplies?: (updateId: string) => Promise<TEntityUpdate[]>;
  onReply?: (parentId: string, description: string) => Promise<void>;
  onEdit?: (updateId: string, description: string, labelIds: string[]) => Promise<void>;
  onDelete?: (updateId: string) => Promise<void>;
}) {
  const [replies, setReplies] = useState<TEntityUpdate[] | null>(null);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editDraft, setEditDraft] = useState(update.description ?? "");
  const [editTopics, setEditTopics] = useState<string[]>(update.label_ids ?? []);
  const { t } = useTranslation();

  const canThread = Boolean(onLoadReplies && onReply);
  const attached = labels.filter((label) => (update.label_ids ?? []).includes(label.id));

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

  const startEditing = () => {
    // Seeded from the update rather than from whatever a previous edit left behind, so
    // cancelling and reopening does not resurrect an abandoned draft.
    setEditDraft(update.description ?? "");
    setEditTopics(update.label_ids ?? []);
    setEditing(true);
  };

  const saveEdit = async () => {
    if (!onEdit) return;
    setBusy(true);
    try {
      await onEdit(update.id, editDraft.trim(), editTopics);
      setEditing(false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="border-t border-subtle pt-3 first:border-t-0 first:pt-0">
      <div className="flex items-center gap-2">
        <UpdateStatusPill status={update.status} />
        <span className="text-11 text-secondary">
          {update.actor_detail?.display_name ?? t("project_overview.activity.someone")}
        </span>
        <time className="text-11 text-tertiary" dateTime={update.created_at}>
          {new Date(update.created_at).toLocaleDateString()}
        </time>
        {/* An announcement changed quietly is worse than one that cannot be changed at all. */}
        {update.is_edited && <span className="text-10 text-tertiary">{t("project_overview.updates.edited")}</span>}
        {canChange && !editing && (
          <span className="ml-auto flex items-center gap-1">
            {onEdit && (
              <button
                type="button"
                aria-label={t("project_overview.updates.edit")}
                className="rounded p-1 text-tertiary hover:bg-surface-2 hover:text-secondary"
                onClick={startEditing}
              >
                <Pencil className="size-3" />
              </button>
            )}
            {onDelete && (
              <button
                type="button"
                aria-label={t("project_overview.updates.delete")}
                className="rounded p-1 text-tertiary hover:bg-surface-2 hover:text-danger-primary"
                onClick={() => void onDelete(update.id)}
              >
                <Trash2 className="size-3" />
              </button>
            )}
          </span>
        )}
      </div>

      {editing ? (
        <div className="mt-2 space-y-2">
          <textarea
            aria-label={t("project_overview.updates.description_label")}
            className="min-h-16 w-full rounded border border-subtle bg-surface-1 px-2 py-1.5 text-12 text-primary outline-none focus:border-accent-strong"
            value={editDraft}
            onChange={(event) => setEditDraft(event.target.value)}
          />
          {!!labels.length && <TopicPicker labels={labels} selected={editTopics} onChange={setEditTopics} />}
          <div className="flex gap-2">
            <button
              type="button"
              className="h-7 rounded bg-accent-primary px-2.5 text-11 font-medium text-inverse disabled:opacity-50"
              disabled={busy}
              onClick={() => void saveEdit()}
            >
              {t("project_overview.updates.save")}
            </button>
            <button
              type="button"
              className="h-7 rounded bg-surface-2 px-2.5 text-11 font-medium text-secondary"
              onClick={() => setEditing(false)}
            >
              {t("project_overview.updates.cancel")}
            </button>
          </div>
        </div>
      ) : (
        <>
          {update.description && <p className="mt-1 text-12 text-primary">{update.description}</p>}
          {!!attached.length && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {attached.map((label) => (
                <TopicChip key={label.id} label={label} />
              ))}
            </div>
          )}
        </>
      )}

      {canThread && !editing && (
        <>
          <button
            type="button"
            className="mt-1 text-11 text-tertiary hover:text-secondary"
            onClick={() => void toggle()}
          >
            {open
              ? t("project_overview.updates.hide_replies")
              : update.reply_count
                ? t("project_overview.updates.reply_count", { count: update.reply_count })
                : t("project_overview.updates.reply")}
          </button>

          {open && (
            <div className="mt-2 space-y-2 border-l border-subtle pl-3">
              {(replies ?? []).map((reply) => (
                <div key={reply.id}>
                  <div className="flex items-center gap-2">
                    <span className="text-11 text-secondary">
                      {reply.actor_detail?.display_name ?? t("project_overview.activity.someone")}
                    </span>
                    <time className="text-11 text-tertiary" dateTime={reply.created_at}>
                      {new Date(reply.created_at).toLocaleDateString()}
                    </time>
                  </div>
                  <p className="text-12 text-primary">{reply.description}</p>
                </div>
              ))}
              {replies !== null && !replies.length && (
                <p className="text-11 text-tertiary">{t("project_overview.updates.no_replies")}</p>
              )}

              {!disabled && (
                <div className="flex gap-2">
                  <input
                    aria-label={t("project_overview.updates.reply_label")}
                    className="h-7 flex-1 rounded border border-subtle bg-surface-1 px-2 text-12 text-primary outline-none focus:border-accent-strong"
                    placeholder={t("project_overview.updates.reply")}
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                  />
                  <button
                    type="button"
                    className="h-7 rounded bg-surface-2 px-2 text-11 font-medium text-primary disabled:opacity-50"
                    disabled={busy || !draft.trim()}
                    onClick={() => void send()}
                  >
                    {t("project_overview.updates.send")}
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
 * The noticeboard: what the team is telling each other about this project.
 *
 * One component for projects and work items because it is one model. The official product
 * shipped updates on epics first and then extended them everywhere, which is the same
 * conclusion arrived at from the other direction.
 *
 * Topics are project labels rather than a fixed set of categories. A hardcoded enum would
 * have to guess whether this team's non-engineering posts are "market", "commercial" or
 * "customer escalation" -- and be wrong for the next team. `Label` already gives per-project
 * scope, a colour and a settings page, so no category name appears anywhere in this file or
 * in the API that serves it.
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
  labels = [],
  currentUserId,
  canModerate = false,
  onEdit,
  onDelete,
}: Props) {
  const [status, setStatus] = useState<TUpdateStatus>("on_track");
  const [description, setDescription] = useState("");
  const [topics, setTopics] = useState<string[]>([]);
  const [posting, setPosting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The full thread, once asked for. Null until then, so `updates` stays the source of
  // truth for the common case and a refetch after posting is not fighting a stale copy.
  const [expanded, setExpanded] = useState<TEntityUpdate[] | null>(null);
  const [expanding, setExpanding] = useState(false);
  // Filtering runs on what is already loaded. The endpoint takes a `label` parameter too,
  // but the board holds ten posts and a round trip to hide two of them would be slower
  // than the click that asked for it.
  const [topicFilter, setTopicFilter] = useState<string | null>(null);
  const { t } = useTranslation();

  const all = expanded ?? updates;
  const shown = topicFilter ? all.filter((update) => (update.label_ids ?? []).includes(topicFilter)) : all;
  const hidden = (total ?? all.length) - all.length;

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
      await onPost(status, description.trim(), topics);
      setDescription("");
      setTopics([]);
    } catch {
      setError(t("project_overview.updates.not_posted"));
    } finally {
      setPosting(false);
    }
  };

  return (
    <section className="rounded border border-subtle p-4">
      <h2 className="text-13 font-medium text-primary">{t("project_overview.updates.title")}</h2>
      <p className="mt-0.5 text-11 text-tertiary">
        {entityName === "project"
          ? t("project_overview.updates.subtitle_project")
          : t("project_overview.updates.subtitle_work_item")}
      </p>

      {/* Only worth a row once the team has actually invented some topics. */}
      {!!labels.length && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5 border-b border-subtle pb-3">
          <button
            type="button"
            aria-pressed={topicFilter === null}
            onClick={() => setTopicFilter(null)}
            className={`rounded px-2 py-0.5 text-10 font-medium ${
              topicFilter === null ? "bg-surface-2 text-primary" : "text-tertiary hover:text-secondary"
            }`}
          >
            {t("project_overview.updates.all_topics")}
          </button>
          {labels.map((label) => {
            const color = label.color || "#a3a3a3";
            const on = topicFilter === label.id;
            return (
              <button
                key={label.id}
                type="button"
                aria-pressed={on}
                onClick={() => setTopicFilter(on ? null : label.id)}
                className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-10 font-medium ${
                  on ? "text-secondary" : "text-tertiary hover:text-secondary"
                }`}
                style={on ? { backgroundColor: `${color}2e` } : undefined}
              >
                <span className="size-1.5 rounded-full" style={{ backgroundColor: color }} />
                {label.name}
              </button>
            );
          })}
          {topicFilter && (
            <button
              type="button"
              aria-label={t("project_overview.updates.clear_filter")}
              className="rounded p-1 text-tertiary hover:text-secondary"
              onClick={() => setTopicFilter(null)}
            >
              <X className="size-3" />
            </button>
          )}
        </div>
      )}

      {!disabled && (
        <div className="mt-3 space-y-2">
          <div className="flex gap-2">
            {(Object.keys(UPDATE_STATUS_KEYS) as TUpdateStatus[]).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setStatus(value)}
                className={`rounded px-2 py-1 text-11 font-medium ${
                  status === value ? STATUS_CLASSES[value] : "bg-surface-2 text-tertiary"
                }`}
              >
                {t(UPDATE_STATUS_KEYS[value])}
              </button>
            ))}
          </div>
          <textarea
            aria-label={t("project_overview.updates.description_label")}
            className="min-h-16 w-full rounded border border-subtle bg-surface-1 px-2 py-1.5 text-12 text-primary outline-none focus:border-accent-strong"
            placeholder={t("project_overview.updates.description_placeholder")}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
          {!!labels.length && <TopicPicker labels={labels} selected={topics} onChange={setTopics} />}
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="h-8 rounded bg-accent-primary px-3 text-12 font-medium text-inverse disabled:opacity-50"
              disabled={posting}
              onClick={() => void submit()}
            >
              {posting ? t("project_overview.updates.posting") : t("project_overview.updates.post")}
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
            labels={labels}
            canChange={canModerate || (!!currentUserId && update.actor_detail?.id === currentUserId)}
            onLoadReplies={onLoadReplies}
            onReply={onReply}
            onEdit={onEdit}
            onDelete={onDelete}
          />
        ))}
        {!shown.length && (
          <li className="text-12 text-tertiary">
            {topicFilter ? t("project_overview.updates.none_in_topic") : t("project_overview.updates.empty")}
          </li>
        )}
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
