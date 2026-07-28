/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TIssueServiceType } from "@plane/types";
import { useWorkItemPropertyDefinitions, useWorkItemPropertyValues } from "./use-work-item-extensions";

export const useWorkItemProperties = (
  projectId: string | null | undefined,
  workspaceSlug: string | null | undefined,
  workItemId: string | null | undefined,
  _issueServiceType: TIssueServiceType
) => {
  useWorkItemPropertyDefinitions(workspaceSlug ?? undefined, projectId ?? undefined);
  useWorkItemPropertyValues(workspaceSlug ?? undefined, projectId ?? undefined, workItemId ?? undefined);
};
