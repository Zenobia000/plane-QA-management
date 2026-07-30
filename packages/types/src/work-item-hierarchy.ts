/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TEpicAnalyticsGroup =
  | "backlog_issues"
  | "unstarted_issues"
  | "started_issues"
  | "completed_issues"
  | "cancelled_issues"
  | "overdue_issues";

export type TEpicAnalytics = {
  backlog_issues: number;
  unstarted_issues: number;
  started_issues: number;
  completed_issues: number;
  cancelled_issues: number;
  overdue_issues: number;
};

export type TWorkItemStateGroup = "backlog" | "unstarted" | "started" | "completed" | "cancelled";

export type TWorkItemAxisSpread = {
  name: string;
  count: number;
};

export type TWorkItemRollup = {
  /** Items at every depth beneath the node, excluding the node itself. */
  descendants: number;
  /**
   * Leaf descendants -- the denominator every other figure here is computed over.
   *
   * Interior nodes are summaries of their own children, so counting a feature beside the
   * stories it summarises would state the same work twice.
   */
  leaves: number;
  state_distribution: Record<TWorkItemStateGroup, number>;
  points: {
    /** Sum of estimate values, not of the 1-based ordinal keys the burndown adds up. */
    total: number;
    sized: number;
    unsized: number;
  };
  coverage: {
    in_scope: number;
    covered: number;
    uncovered: number;
    /** Worst verification status across everything beneath, or null when nothing ran. */
    latest_status: string | null;
  };
  cycles: TWorkItemAxisSpread[];
  milestones: TWorkItemAxisSpread[];
  modules: TWorkItemAxisSpread[];
};

export type TWorkItemNode = {
  id: string;
  sequence_id: number;
  name: string;
  priority: string;
  type: { id: string; name: string; is_epic: boolean } | null;
  state: { id: string; name: string; group: TWorkItemStateGroup } | null;
  estimate_point: number | null;
  milestone: string | null;
  /** True when nothing sits beneath it, in which case `rollup` is empty by construction. */
  is_leaf: boolean;
  /** This node's own inherited coverage verdict, distinct from the rollup ratio. */
  covered: boolean;
  latest_status: string | null;
  children: TWorkItemNode[];
  rollup: TWorkItemRollup;
};

/**
 * The response shape of both hierarchy reads.
 *
 * Asking for a project returns every root; asking for one work item returns a single-node
 * list holding that item's subtree. Same shape either way, because it is the same
 * computation with a different starting point.
 */
export type TWorkItemHierarchy = {
  nodes: TWorkItemNode[];
};

/** @deprecated Epic is a work item type, not a separate hierarchy. Use the TWorkItem* names. */
export type TEpicStateGroup = TWorkItemStateGroup;
/** @deprecated Use {@link TWorkItemAxisSpread}. */
export type TEpicAxisSpread = TWorkItemAxisSpread;
/** @deprecated Use {@link TWorkItemRollup}. */
export type TEpicRollup = TWorkItemRollup;
/** @deprecated Use {@link TWorkItemNode}. */
export type TEpicNode = TWorkItemNode;
/** @deprecated Use {@link TWorkItemHierarchy}. */
export type TEpicHierarchy = TWorkItemHierarchy;
