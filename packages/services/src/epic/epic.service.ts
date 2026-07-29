/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { TEpicHierarchy } from "@plane/types";
import { APIService } from "../api.service";

export class EpicService extends APIService {
  constructor(BASE_URL?: string) {
    super(BASE_URL || API_BASE_URL);
  }

  /**
   * The whole tree in one request.
   *
   * Walking it client-side by calling the sub-issues endpoint per node would be an N+1
   * against a structure that is read as a whole, and the coverage aggregate is not
   * derivable from sub-issue payloads at all -- it needs the same recursive pass the
   * coverage report already makes server-side.
   */
  async getHierarchy(workspaceSlug: string, projectId: string): Promise<TEpicHierarchy> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/epic-hierarchy/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
