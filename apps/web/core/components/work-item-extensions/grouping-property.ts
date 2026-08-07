/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TWorkItemProperty } from "@plane/types";

/**
 * The one property an intake form may ask a reporter for, if any.
 *
 * The project overview groups its intake panel by whichever property carries
 * `is_grouping_dimension`, and until this existed nothing in the UI could set that value:
 * every item filed through intake landed in the panel's untagged pile. This is the rule
 * that decides whether the intake form grows that one field.
 *
 * Three ways it comes back empty, all of them cases where showing the field would lie:
 *
 * - **The caller may not write property values.** Filing an intake item needs GUEST;
 *   `WorkItemPropertyValueDetailEndpoint` needs MEMBER. A field a reporter can fill and
 *   not save is worse than no field, because it looks like it worked.
 * - **The dimension is narrowed to a work item type.** Intake creates an item with no
 *   type, and the value endpoint refuses a property whose type the item does not carry.
 * - **No dimension, or an inactive one.** The project has not opted into grouping.
 *
 * At most one property per project can hold the flag -- the database enforces it -- so
 * the first match is the match.
 */
export function intakeGroupingProperty(
  definitions: TWorkItemProperty[] | undefined,
  canSetPropertyValues: boolean
): TWorkItemProperty | undefined {
  if (!canSetPropertyValues) return undefined;
  return (definitions ?? []).find(
    (definition) => definition.is_active && definition.is_grouping_dimension && !definition.type
  );
}
