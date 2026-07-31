/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/** The portfolio vocabulary, shared with milestones and initiatives. */
export type TPortfolioStatus = "planned" | "in_progress" | "completed" | "cancelled";

/** The three-way health signal an update carries. Deliberately not {@link TPortfolioStatus}. */
export type TUpdateStatus = "on_track" | "at_risk" | "off_track";

export type TUpdateEntityName = "project" | "work_item";

export type TProjectProgress = {
  state_distribution: Record<"backlog" | "unstarted" | "started" | "completed" | "cancelled", number>;
  total: number;
  /** Total less cancelled work. Cancelled items are out of scope, not outstanding. */
  in_scope: number;
  completed: number;
  completion_percentage: number;
};

export type TProjectOverviewLink = {
  id: string;
  title: string | null;
  url: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type TEntityUpdate = {
  id: string;
  entity_name: TUpdateEntityName;
  entity_identifier: string;
  status: TUpdateStatus;
  description: string;
  parent: string | null;
  reply_count: number;
  actor_detail: {
    id: string;
    display_name: string;
    avatar_url: string | null;
  } | null;
  created_at: string;
};

export type TEntityUpdatePayload = {
  entity_name: TUpdateEntityName;
  entity_identifier: string;
  status: TUpdateStatus;
  description?: string;
  parent?: string | null;
};

export type TProjectActivityEvent = {
  id: string;
  verb: string;
  field: string | null;
  old_value: string | null;
  new_value: string | null;
  comment: string;
  created_at: string;
  actor: {
    id: string;
    display_name: string;
    avatar_url: string | null;
  } | null;
  /** Null for events about the project itself rather than about a work item in it. */
  work_item: { id: string; name: string } | null;
};

/**
 * One page of activity, cursor-paginated.
 *
 * The service used to narrow the response to `{ results }`, which discarded the cursor at
 * the type level and left the client unable to ask for a second page even in principle --
 * so it rendered whatever a single request returned, however long that was.
 */
export type TProjectActivityPage = {
  results: TProjectActivityEvent[];
  next_cursor: string;
  next_page_results: boolean;
  total_count: number;
};

export type TProjectMilestoneSummary = {
  id: string;
  name: string;
  status: TPortfolioStatus;
  target_date: string | null;
  total: number;
  completed: number;
};

/** The one request the overview page makes for everything not already on the project. */
export type TProjectOverview = {
  progress: TProjectProgress;
  links: TProjectOverviewLink[];
  updates: TEntityUpdate[];
  milestones: TProjectMilestoneSummary[];
};
