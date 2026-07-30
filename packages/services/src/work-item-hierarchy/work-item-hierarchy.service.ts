/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { TWorkItemHierarchy } from "@plane/types";
import { APIService } from "../api.service";

export class WorkItemHierarchyService extends APIService {
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
  async getProjectHierarchy(workspaceSlug: string, projectId: string): Promise<TWorkItemHierarchy> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-hierarchy/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * One work item's own subtree, in the same shape.
   *
   * Nothing about this is Epic-specific: a feature reporting on its stories asks the same
   * question an epic does, so it uses the same call rather than a parallel one.
   */
  async getSubtree(workspaceSlug: string, projectId: string, workItemId: string): Promise<TWorkItemHierarchy> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-items/${workItemId}/hierarchy/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}

/** @deprecated Epic is a work item type, not a separate hierarchy. Use {@link WorkItemHierarchyService}. */
export const EpicService = WorkItemHierarchyService;
