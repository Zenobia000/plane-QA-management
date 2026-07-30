/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/** One legal move between two states. Absence of any edge out of a state means unconstrained. */
export type TStateTransition = {
  id: string;
  from_state: string;
  to_state: string;
  requires_approval: boolean;
  approvers: string[];
};

export type TStateTransitionPayload = {
  from_state: string;
  to_state: string;
  requires_approval?: boolean;
  approver_ids?: string[];
};

/** Time logged against a work item, in whole minutes. */
export type TWorklog = {
  id: string;
  issue: string;
  logged_by: string;
  duration: number;
  description: string;
  logged_at: string;
};

export type TWorklogSummary = {
  duration: number;
  by_member: { member_id: string; display_name: string; duration: number }[];
};

export type TTemplateKind = "work_item" | "project";

export type TTemplate = {
  id: string;
  kind: TTemplateKind;
  name: string;
  description: string;
  project: string | null;
  payload: Record<string, unknown>;
};

export type TTeamspace = {
  id: string;
  name: string;
  description: string;
  logo_props: Record<string, unknown>;
  member_ids: string[];
  project_ids: string[];
};

export type TInitiative = {
  id: string;
  name: string;
  description: string;
  status: "planned" | "in_progress" | "completed" | "cancelled";
  target_date: string | null;
  project_ids: string[];
};

export type TInitiativeProgress = {
  project_count: number;
  state_distribution: Record<string, number>;
  total: number;
  in_scope: number;
  completed: number;
  completion_percentage: number;
};

export type TDashboard = {
  id: string;
  name: string;
  description: string;
  access: number;
};

export type TDashboardWidget = {
  id: string;
  name: string;
  entity: "work_item";
  group_by: "state_group" | "priority" | "assignee" | "project";
  chart: "bar" | "donut" | "number";
  project_ids: string[];
  sort_order: number;
};

export type TDashboardWidgetData = {
  widget_id: string;
  group_by: TDashboardWidget["group_by"];
  chart: TDashboardWidget["chart"];
  total: number;
  series: { key: string; label: string; count: number }[];
};

/** A work item that looks like the one being written. `similarity` is null on the fallback path. */
export type TDuplicateCandidate = {
  id: string;
  name: string;
  sequence_id: number;
  similarity: number | null;
};
