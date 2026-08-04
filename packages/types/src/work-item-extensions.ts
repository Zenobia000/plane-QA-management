/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import type { TLogoProps } from "./common";

export type TWorkItemType = {
  id: string;
  name: string;
  description: string;
  logo_props: TLogoProps | Record<string, never>;
  is_epic: boolean;
  is_default: boolean;
  is_active: boolean;
  /**
   * Whether work items of this type are promises the product makes, and so owe an
   * acceptance test. The requirement-coverage report counts only these.
   *
   * Set per type rather than derived from its name: types are workspace-owned and get
   * renamed, and a check against "Story" would report perfect coverage the day someone
   * translated it. Defaults true, so an unclassified type shows up as noise rather than
   * disappearing from the report.
   */
  needs_acceptance: boolean;
  level: number;
  created_at: string;
  updated_at: string;
};

export type TProjectWorkItemType = {
  id: string;
  type: TWorkItemType;
  level: number;
  is_default: boolean;
  project: string;
  workspace: string;
  created_at: string;
  updated_at: string;
};

export type TWorkItemPropertyKind = "text" | "number" | "date" | "boolean" | "select" | "multi_select" | "url";

export type TWorkItemPropertyOption = {
  id?: string;
  label: string;
  value: string;
  sort_order: number;
};

export type TWorkItemProperty = {
  id: string;
  name: string;
  description: string;
  kind: TWorkItemPropertyKind;
  is_required: boolean;
  is_active: boolean;
  /**
   * Whether the project overview groups its intake panel by this property.
   *
   * At most one per project, enforced by the database. Only a select or multi-select can
   * carry it -- grouping by free text makes one bucket per typo.
   */
  is_grouping_dimension: boolean;
  sort_order: number;
  default_value: unknown;
  options: TWorkItemPropertyOption[];
  /**
   * The work item type this property is narrowed to, or null for every type.
   *
   * Null is the pre-existing case and stays the common one -- a project-wide field. Set,
   * it means only items of that type are asked for the value.
   */
  type: string | null;
  project: string;
  workspace: string;
  created_at: string;
  updated_at: string;
};

export type TWorkItemPropertyValue = {
  id: string;
  property: TWorkItemProperty;
  value: unknown;
  issue: string;
  project: string;
  workspace: string;
  created_at: string;
  updated_at: string;
};

export type TPaginatedWorkItemExtensionResponse<T> = {
  results: T[];
  total_count?: number;
  next_cursor?: string | null;
};
