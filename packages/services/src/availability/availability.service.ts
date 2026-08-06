/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { TAvailabilityCapabilities } from "@plane/types";
import { APIService } from "../api.service";

/**
 * Availability hangs off the workspace, not a project.
 *
 * That is the whole argument of ADR 0008 in one URL shape: an absence is a fact about a
 * person, and a person is a member of the workspace. Every path here therefore takes a
 * slug and no project id.
 */
export class AvailabilityService extends APIService {
  constructor(BASE_URL?: string) {
    super(BASE_URL || API_BASE_URL);
  }

  async getCapabilities(workspaceSlug: string): Promise<TAvailabilityCapabilities> {
    return this.get(`/api/workspaces/${workspaceSlug}/availability/capabilities/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
