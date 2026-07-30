/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IProjectIssues } from "@/store/issue/project";
import { ProjectIssues } from "@/store/issue/project";

export type IProjectEpics = IProjectIssues;

/**
 * The project work-item store, reading through the epic-scoped filters.
 *
 * It adds nothing of its own on purpose. Every fetch path -- first page, next page, refetch
 * with stored pagination -- goes through `issueFilterStore.getFilterParams`, so scoping
 * belongs there and doing it here as well would be two places to keep in agreement. An epic
 * is an ordinary work item, so create, update, delete and grouping are the inherited ones.
 */
export class ProjectEpics extends ProjectIssues implements IProjectEpics {}
