/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import { APIService } from "../api.service";

export default class IntakeIssueService extends APIService {
  constructor(BASE_URL?: string) {
    super(BASE_URL || API_BASE_URL);
  }

  async list(workspaceSlug: string, projectId: string, params = {}) {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/inbox-issues/`, {
      params,
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Retriage one piece of intake.
   *
   * Keyed by the work item's id, not the intake row's -- that is what the endpoint looks
   * itself up by, and getting it the other way round returns a 404 that reads like a
   * permissions problem.
   *
   * Only project admins may change the status; the endpoint enforces it, and callers
   * should hide the control rather than let it fail after the click.
   */
  async triage(workspaceSlug: string, projectId: string, issueId: string, payload: { status: number }) {
    return this.patch(`/api/workspaces/${workspaceSlug}/projects/${projectId}/intake-issues/${issueId}/`, payload)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}

export { IntakeIssueService };
