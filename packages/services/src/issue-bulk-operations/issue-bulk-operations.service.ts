/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import { APIService } from "../api.service";

export class IssueBulkOperationsService extends APIService {
  constructor(BASE_URL?: string) {
    super(BASE_URL || API_BASE_URL);
  }

  /**
   * Apply one set of properties to a selection.
   *
   * The endpoint refuses per-item properties rather than ignoring them, so a caller that
   * sends `name` gets a 400 instead of a silent no-op.
   */
  async update(
    workspaceSlug: string,
    projectId: string,
    issueIds: string[],
    properties: Record<string, unknown>
  ): Promise<{ updated: number }> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/bulk-update-issues/`, {
      issue_ids: issueIds,
      properties,
    })
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
