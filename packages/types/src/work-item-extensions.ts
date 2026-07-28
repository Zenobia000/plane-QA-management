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
  sort_order: number;
  default_value: unknown;
  options: TWorkItemPropertyOption[];
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
