/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TWorkItemProperty } from "@plane/types";

/**
 * The properties a work item of this type is asked for.
 *
 * A property with no `type` belongs to the whole project and is shown on everything, which
 * is what every property created before narrowing existed does. A narrowed one appears only
 * on its own type.
 *
 * The server enforces the same rule on both write paths; this is what stops the form asking
 * for a value the API would then refuse. Kept in one place because the modal and the detail
 * sidebar have to agree -- if they drifted, a field would be fillable in one and rejected on
 * save from the other.
 */
export function propertiesForType(
  definitions: TWorkItemProperty[] | undefined,
  workItemTypeId: string | null | undefined
): TWorkItemProperty[] {
  return (definitions ?? []).filter(
    (definition) => definition.is_active && (!definition.type || definition.type === workItemTypeId)
  );
}
