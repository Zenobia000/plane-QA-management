/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TWorkItemProperty } from "@plane/types";

/** What the caller learned from trying to attribute the new work item. */
export type TGroupingWriteOutcome = "saved" | "skipped" | "failed";

/** The one method this needs, so a spec can pass a stub instead of a configured service. */
type TPropertyValueWriter = {
  setPropertyValue: (
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    propertyId: string,
    value: unknown
  ) => Promise<unknown>;
};

type TPersistGroupingValue = {
  definition: TWorkItemProperty | undefined;
  issueId: string;
  projectId: string;
  service: TPropertyValueWriter;
  value: unknown;
  workspaceSlug: string;
};

const isEmpty = (value: unknown) =>
  value === null || value === undefined || value === "" || (Array.isArray(value) && value.length === 0);

/** Whether a required grouping dimension was left blank, which should stop the submit. */
export function isGroupingValueMissing(definition: TWorkItemProperty | undefined, value: unknown): boolean {
  if (!definition?.is_required) return false;
  return isEmpty(value);
}

/**
 * Attribute a freshly created intake item, reporting what happened rather than throwing.
 *
 * Intake creation and property writes are two requests and cannot be one transaction: the
 * item id only exists after the first. So the second can fail on its own -- a role that
 * may file but not attribute, a property deactivated between load and submit -- and the
 * work item is still there. Swallowing that would let the form claim a plain success for
 * an item that landed untagged; throwing would make the caller treat a created item as a
 * failed creation. Neither is true, so the outcome is returned instead.
 */
export async function persistGroupingValue({
  definition,
  issueId,
  projectId,
  service,
  value,
  workspaceSlug,
}: TPersistGroupingValue): Promise<TGroupingWriteOutcome> {
  if (!definition || isEmpty(value)) return "skipped";
  try {
    await service.setPropertyValue(workspaceSlug, projectId, issueId, definition.id, value);
    return "saved";
  } catch {
    return "failed";
  }
}
