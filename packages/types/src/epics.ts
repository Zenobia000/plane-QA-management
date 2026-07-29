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

export type TEpicStateGroup = "backlog" | "unstarted" | "started" | "completed" | "cancelled";

export type TEpicAxisSpread = {
  name: string;
  count: number;
};

export type TEpicRollup = {
  /** Descendants at every depth, excluding the node itself. */
  descendants: number;
  state_distribution: Record<TEpicStateGroup, number>;
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
  cycles: TEpicAxisSpread[];
  milestones: TEpicAxisSpread[];
  modules: TEpicAxisSpread[];
};

export type TEpicNode = {
  id: string;
  sequence_id: number;
  name: string;
  priority: string;
  type: { id: string; name: string; is_epic: boolean } | null;
  state: { id: string; name: string; group: TEpicStateGroup } | null;
  estimate_point: number | null;
  milestone: string | null;
  children: TEpicNode[];
  rollup: TEpicRollup;
};

export type TEpicHierarchy = {
  nodes: TEpicNode[];
};
