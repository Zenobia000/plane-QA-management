/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { TEpicAnalytics } from "@plane/types";
import { APIService } from "../api.service";

export class EpicService extends APIService {
  constructor(BASE_URL?: string) {
    super(BASE_URL || API_BASE_URL);
  }

  /**
   * State-group counts for the work beneath one epic.
   *
   * Separate from the epic row itself because it is a different cardinality -- one row
   * versus a whole subtree -- and the list never needs it. Folding it into the work-item
   * payload would make every list page pay for a tree walk it does not render.
   */
  async getAnalytics(workspaceSlug: string, projectId: string, epicId: string): Promise<TEpicAnalytics> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/epics/${epicId}/analytics/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
