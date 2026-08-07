/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { type Dispatch, type SetStateAction, useMemo, useState } from "react";
import { Pencil, Tag, Trash2, X } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import type { IIssueLabel, TEntityUpdate, TUpdateEntityName, TUpdateStatus } from "@plane/types";
import { CustomSearchSelect } from "@plane/ui";
import { BoardControls, SectionHeader } from "./board-controls";
import { SECTION_PREVIEW, type TBoardGrouping, type TBoardSort, groupUpdates, overlap, sortUpdates } from "./shape";
import { STATUS_CLASSES, UPDATE_STATUS_KEYS } from "./status";
import { UpdateStatusPill } from "./status-pill";

/**
 * How many topics the filter row shows before collapsing the rest behind a toggle.
 *
 * A project with four topics should not pay for a control it does not need, and one with
 * twenty should not push the composer off the screen. Six is roughly one line at the
 * panel's width.
 */
const VISIBLE_TOPIC_FILTERS = 6;

/**
 * Add or remove one section key from a set of them.
 *
 * Module scope rather than inside the panel: it closes over nothing, so rebuilding it on
 * every render only costs work and defeats memoisation downstream.
 */
const toggleKey = (setter: Dispatch<SetStateAction<Set<string>>>, key: string) =>
  setter((current) => {
    const next = new Set(current);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    return next;
  });

// Re-exported so importers of this module keep the surface they had before the pill moved
// out to break a cycle with `board-controls.tsx`.
export { STATUS_CLASSES, UPDATE_STATUS_KEYS, UpdateStatusPill };

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

/**
 * Topic selection for the post being written.
 *
 * A dropdown rather than a row of toggle chips, for two reasons that turned out to be one.
 * Visually, the chips were indistinguishable from the filter row a few lines above -- same
 * shape, same colours, same order -- so the panel appeared to draw one control twice, and
 * nothing said which narrowed the reading and which tagged the writing. Structurally, both
 * were unbounded `flex-wrap`: at seven topics each already filled a line, and a team that
 * keeps inventing them pushes the composer down the page twice over.
 *
 * Filtering stays chips because it is a view control the reader scans. Tagging is form
 * input and belongs in the form.
 */
function TopicSelect({
  labels,
  selected,
  onChange,
}: {
  labels: IIssueLabel[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  const { t } = useTranslation();

  const options = useMemo(
    () =>
      labels.map((label) => ({
        value: label.id,
        query: label.name,
        content: (
          <span className="flex items-center gap-1.5">
            <span className="size-2 rounded-full" style={{ backgroundColor: label.color || "#a3a3a3" }} />
            <span className="truncate">{label.name}</span>
          </span>
        ),
      })),
    [labels]
  );

  const chosen = labels.filter((label) => selected.includes(label.id));

  return (
    <CustomSearchSelect
      multiple
      value={selected}
      options={options}
      onChange={(next: string[]) => onChange(next)}
      maxHeight="md"
      buttonClassName="w-full rounded border border-subtle px-2 py-1 text-10 font-medium"
      noResultsMessage={t("project_overview.updates.no_topics_found")}
      label={
        <span className="flex items-center gap-1.5">
          <Tag className="size-3 flex-shrink-0 text-tertiary" />
          {chosen.length === 0 ? (
            <span className="text-tertiary">{t("project_overview.updates.add_topics")}</span>
          ) : (
            // Named, not counted. "2 topics" would make the writer reopen the dropdown to
            // find out which two.
            <span className="flex flex-wrap items-center gap-1">
              {chosen.map((label) => (
                <span
                  key={label.id}
                  className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-secondary"
                  style={{ backgroundColor: `${label.color || "#a3a3a3"}1f` }}
                >
                  <span className="size-1.5 rounded-full" style={{ backgroundColor: label.color || "#a3a3a3" }} />
                  {label.name}
                </span>
              ))}
            </span>
          )}
        </span>
      }
    />
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
          {!!labels.length && <TopicSelect labels={labels} selected={editTopics} onChange={setEditTopics} />}
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
  const [showAllTopics, setShowAllTopics] = useState(false);
  // How the board is read. Both default to what the endpoint already returns, so a reader
  // who touches nothing sees exactly the board that existed before these controls did.
  const [sort, setSort] = useState<TBoardSort>("newest");
  const [grouping, setGrouping] = useState<TBoardGrouping>("none");
  // Sections the reader folded shut, and sections they asked past the preview. Both are
  // keyed by section rather than by index, so a new post arriving does not reassign them.
  const [closedSections, setClosedSections] = useState<Set<string>>(new Set());
  const [openedInFull, setOpenedInFull] = useState<Set<string>>(new Set());

  // The active filter is always shown, wherever it sits in the list. Collapsing the row
  // while it is filtering by something now hidden would leave the reader looking at a
  // narrowed board with nothing on screen saying why.
  const visibleFilterLabels = useMemo(() => {
    if (showAllTopics || labels.length <= VISIBLE_TOPIC_FILTERS) return labels;
    const head = labels.slice(0, VISIBLE_TOPIC_FILTERS);
    const active = labels.find((label) => label.id === topicFilter);
    return active && !head.includes(active) ? [...head, active] : head;
  }, [labels, showAllTopics, topicFilter]);
  const hiddenFilterCount = labels.length - visibleFilterLabels.length;
  const { t } = useTranslation();

  const all = expanded ?? updates;
  const hidden = (total ?? all.length) - all.length;

  const shown = useMemo(
    () => (topicFilter ? all.filter((update) => (update.label_ids ?? []).includes(topicFilter)) : all),
    [all, topicFilter]
  );
  const sections = useMemo(
    () => groupUpdates(sortUpdates(shown, sort), grouping, labels),
    [shown, sort, grouping, labels]
  );
  // Positive only when a post carries several topics and so appears under each.
  const extraRows = overlap(sections, shown);

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

  /**
   * Reordering a partly-loaded board would rank ten of forty posts and present the answer
   * as the board's worst-first order -- the escalation the reader was looking for could sit
   * in the thirty nobody fetched. So anything that changes the order pulls the rest first.
   *
   * The default view is exempt: newest-first ungrouped is the order the endpoint already
   * returned, so the embedded page is a true prefix of it.
   */
  const reorder = <T,>(apply: (next: T) => void, isDefault: (next: T) => boolean) => {
    return (next: T) => {
      apply(next);
      if (!isDefault(next) && !expanded && hidden > 0) void showAll();
    };
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
          {visibleFilterLabels.map((label) => {
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
          {hiddenFilterCount > 0 && (
            <button
              type="button"
              onClick={() => setShowAllTopics((open) => !open)}
              className="rounded px-2 py-0.5 text-10 font-medium text-tertiary hover:text-secondary"
            >
              {showAllTopics
                ? t("project_overview.updates.show_fewer_topics")
                : t("project_overview.updates.more_topics", { count: hiddenFilterCount })}
            </button>
          )}
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
          {!!labels.length && <TopicSelect labels={labels} selected={topics} onChange={setTopics} />}
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

      {/* Not worth a control until there is something to reorder. */}
      {shown.length > 1 && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-1.5">
          <BoardControls
            sort={sort}
            grouping={grouping}
            onSort={reorder(setSort, (next) => next === "newest")}
            onGrouping={reorder(setGrouping, (next) => next === "none")}
          />
          {/* The section counts below add up to more than the board holds when a post is
              filed under two topics. Saying so beats arithmetic that reads as a bug. */}
          {extraRows > 0 && (
            <p className="text-10 text-tertiary">
              {t("project_overview.updates.sections_overlap", { count: extraRows })}
            </p>
          )}
        </div>
      )}

      <div className="mt-3 space-y-3">
        {sections.map((section) => {
          const grouped = grouping !== "none";
          const open = !closedSections.has(section.key);
          const inFull = openedInFull.has(section.key);
          // The cap is the point of the whole control: a board that renders everything it
          // has is the running log the reader was complaining about.
          const visible = inFull ? section.updates : section.updates.slice(0, SECTION_PREVIEW);
          const rest = section.updates.length - visible.length;

          return (
            <div key={section.key}>
              {grouped && (
                <SectionHeader
                  section={section}
                  open={open}
                  onToggle={() => toggleKey(setClosedSections, section.key)}
                />
              )}
              {open && (
                <>
                  <ul className={`space-y-3 ${grouped ? "mt-1 pl-5" : ""}`}>
                    {visible.map((update) => (
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
                  </ul>
                  {/* Distinct from "load earlier" below: these are already fetched and
                      merely folded, so the control says so and costs no round trip. */}
                  {rest > 0 && (
                    <button
                      type="button"
                      className={`mt-2 text-11 font-medium text-accent-primary hover:underline ${grouped ? "ml-5" : ""}`}
                      onClick={() => toggleKey(setOpenedInFull, section.key)}
                    >
                      {t("project_overview.updates.show_rest", { count: rest })}
                    </button>
                  )}
                </>
              )}
            </div>
          );
        })}
        {!sections.length && (
          <p className="text-12 text-tertiary">
            {topicFilter ? t("project_overview.updates.none_in_topic") : t("project_overview.updates.empty")}
          </p>
        )}
      </div>
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
