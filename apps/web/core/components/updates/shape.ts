/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IIssueLabel, TEntityUpdate, TUpdateStatus } from "@plane/types";

/**
 * What shape the noticeboard is read in, as opposed to what it says.
 *
 * A board that only ever renders newest-first is a running log: past a couple of dozen
 * posts the escalation that moves the release date sits below three notes about a topic
 * nobody is waiting on, and the only way to find it is to read everything. Ordering,
 * grouping and how much of each group is shown are therefore reader-side decisions, and
 * they live here rather than in the panel so they can be asserted directly -- the rule
 * "off track before at risk" is a claim about the product, not about JSX.
 *
 * Everything in this module is pure and total. Nothing here knows a topic's name: topics
 * are project labels, so the vocabulary belongs to the team and only the ids reach this
 * code.
 */

export const BOARD_SORTS = ["newest", "oldest", "severity"] as const;
export type TBoardSort = (typeof BOARD_SORTS)[number];

export const BOARD_GROUPINGS = ["none", "status", "topic"] as const;
export type TBoardGrouping = (typeof BOARD_GROUPINGS)[number];

/** How many posts a section shows before the rest collapse behind a control. */
export const SECTION_PREVIEW = 3;

/**
 * Worst first. `status` is a health verdict, and the reason to sort by it is to put the
 * thing that is going wrong at the top -- so the order is fixed here rather than taken
 * from the order the statuses happen to be declared in.
 */
const SEVERITY_RANK: Record<TUpdateStatus, number> = { off_track: 0, at_risk: 1, on_track: 2 };

/** Sections render in this order when grouping by status, for the same reason. */
const STATUS_SECTION_ORDER: TUpdateStatus[] = ["off_track", "at_risk", "on_track"];

/** The bucket for posts carrying no topic. Not a label id, so it cannot collide with one. */
export const UNTAGGED_SECTION = "__untagged__";

export type TBoardSection = {
  /** Stable identity for React and for the collapse state. A label id, a status, or the sentinel. */
  key: string;
  /** Set when the heading is a status, so the panel can render its own pill and translation. */
  status?: TUpdateStatus;
  /** Set when the heading is a topic. Absent for the untagged bucket, which the panel names. */
  label?: IIssueLabel;
  updates: TEntityUpdate[];
};

const time = (update: TEntityUpdate) => new Date(update.created_at).getTime();

/**
 * Newest, oldest, or worst-first.
 *
 * Returns a new array: the caller's list is the fetched response, and mutating it would
 * make a re-render depend on which sort ran last.
 *
 * `severity` breaks ties by recency rather than leaving them to the input order, so two
 * posts of the same status do not swap places when an unrelated one is added.
 */
export function sortUpdates(updates: TEntityUpdate[], sort: TBoardSort): TEntityUpdate[] {
  const sorted = [...updates];
  if (sort === "severity") {
    return sorted.sort((a, b) => SEVERITY_RANK[a.status] - SEVERITY_RANK[b.status] || time(b) - time(a));
  }
  return sorted.sort((a, b) => (sort === "oldest" ? time(a) - time(b) : time(b) - time(a)));
}

/**
 * The board as one list, or split into collapsible sections.
 *
 * Within a section the incoming order is preserved, so `sortUpdates` decides the order once
 * and grouping never silently re-sorts underneath it.
 *
 * Grouping by topic puts a post under every topic it carries, which is the honest rendering
 * of an announcement that is about both a customer commitment and a cross-team dependency.
 * It also means the section counts can sum to more than the number of posts -- `overlap()`
 * exists so the panel can say so rather than presenting arithmetic that looks wrong.
 *
 * Empty sections are dropped. A heading for a status nobody has posted is furniture.
 */
export function groupUpdates(
  updates: TEntityUpdate[],
  grouping: TBoardGrouping,
  labels: IIssueLabel[]
): TBoardSection[] {
  if (grouping === "none") return updates.length ? [{ key: "all", updates }] : [];

  if (grouping === "status") {
    return STATUS_SECTION_ORDER.map((status) => ({
      key: status,
      status,
      updates: updates.filter((update) => update.status === status),
    })).filter((section) => section.updates.length > 0);
  }

  // One pass over the posts rather than one scan of the board per topic: a project with
  // twenty topics and a long board would otherwise re-read every post twenty times. The
  // single pass also fixes the order for free -- posts land in each bucket in the order
  // they arrived, which is the order `sortUpdates` chose.
  const known = new Set(labels.map((label) => label.id));
  const byTopic = new Map<string, TEntityUpdate[]>();
  const untagged: TEntityUpdate[] = [];

  for (const update of updates) {
    let filed = false;
    for (const id of update.label_ids ?? []) {
      // A topic deleted from project settings leaves its id behind on the post. Skipping
      // it here and letting the post fall through to `untagged` keeps the announcement on
      // the board; matching on it would create a heading with no name.
      if (!known.has(id)) continue;
      filed = true;
      const bucket = byTopic.get(id);
      if (bucket) bucket.push(update);
      else byTopic.set(id, [update]);
    }
    if (!filed) untagged.push(update);
  }

  // Topic order follows the project's own label order, so the board agrees with the filter
  // row above it and with project settings. Topics nobody has posted under never appear.
  const sections: TBoardSection[] = [];
  for (const label of labels) {
    const inTopic = byTopic.get(label.id);
    if (inTopic?.length) sections.push({ key: label.id, label, updates: inTopic });
  }

  // Last, and never hidden: this is the pile nobody has filed, and a board that drops it
  // reports a tidier noticeboard than the one that exists.
  if (untagged.length) sections.push({ key: UNTAGGED_SECTION, updates: untagged });

  return sections;
}

/**
 * How many more rows the sections show than there are posts.
 *
 * Zero unless a post is filed under several topics. The panel renders a sentence when this
 * is positive; without it the section counts add up to more than the board's own total and
 * the only available reading is that one of them is wrong.
 */
export function overlap(sections: TBoardSection[], updates: TEntityUpdate[]): number {
  return sections.reduce((running, section) => running + section.updates.length, 0) - updates.length;
}
