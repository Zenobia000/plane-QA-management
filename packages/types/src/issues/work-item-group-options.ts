/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * One column heading for a work-item list grouped by parent.
 *
 * Identity only. The grouped page already carries each group's count, and a parent's own
 * progress is a roll-up -- recomputing either here would give the heading a second source
 * for a number the page has already answered.
 */
export type TWorkItemParentGroupOption = {
  id: string;
  name: string;
  sequence_id: number;
  /** Null where a project has not enabled work item types; the heading then renders bare. */
  type_id: string | null;
};
