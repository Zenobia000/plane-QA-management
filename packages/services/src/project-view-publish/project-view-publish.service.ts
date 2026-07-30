/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { TViewPublishSettings } from "@plane/types";
import { APIService } from "../api.service";

export class ProjectViewPublishService extends APIService {
  constructor(BASE_URL?: string) {
    super(BASE_URL || API_BASE_URL);
  }

  async getSettings(workspaceSlug: string, projectId: string, viewId: string): Promise<TViewPublishSettings> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/views/${viewId}/publish/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async publish(
    workspaceSlug: string,
    projectId: string,
    viewId: string,
    payload: Partial<TViewPublishSettings>
  ): Promise<TViewPublishSettings> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/views/${viewId}/publish/`, payload)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async unpublish(workspaceSlug: string, projectId: string, viewId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/views/${viewId}/publish/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
