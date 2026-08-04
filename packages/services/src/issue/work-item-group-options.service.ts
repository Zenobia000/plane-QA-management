/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { TWorkItemParentGroupOption } from "@plane/types";
import { APIService } from "../api.service";

/**
 * Column headings for the groupings whose values are work items rather than settings.
 *
 * States, cycles, modules and members all arrive when a project opens, so grouping by them
 * needs nothing extra. Parents do: they are work items, and the list holds only the page it
 * is showing -- which under `leaf_only` is exactly the page without them.
 */
export class WorkItemGroupOptionService extends APIService {
  constructor(BASE_URL?: string) {
    super(BASE_URL || API_BASE_URL);
  }

  async listParentOptions(workspaceSlug: string, projectId: string): Promise<TWorkItemParentGroupOption[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-group-options/parent/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
