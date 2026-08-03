/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type {
  TProjectAttention,
  TProjectFrontline,
  TEntityUpdate,
  TEntityUpdatePayload,
  TMilestone,
  TMilestonePayload,
  TProjectActivityPage,
  TProjectOverviewLink,
  TProjectOverview,
  TUpdateEntityName,
} from "@plane/types";
import { APIService } from "../api.service";

export class ProjectOverviewService extends APIService {
  constructor(BASE_URL?: string) {
    super(BASE_URL || API_BASE_URL);
  }

  /**
   * Progress, links and the latest updates in one request.
   *
   * The page renders as a unit and every part of it is cheap, so three round trips would
   * only buy the ability to show a third of a screen sooner.
   */
  async getOverview(workspaceSlug: string, projectId: string): Promise<TProjectOverview> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/overview/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * One page of activity. Pass the previous page's `next_cursor` to continue.
   *
   * The whole envelope is returned, not just `results` -- without the cursor the caller
   * has no way to reach a second page, which is how this ended up rendering every row the
   * server was willing to send.
   */
  async getActivity(workspaceSlug: string, projectId: string, cursor?: string): Promise<TProjectActivityPage> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/activity/`, {
      params: cursor ? { cursor } : undefined,
    })
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Intake grouped by the project's chosen dimension.
   *
   * Separate from `getOverview` because it is the one part of the page a project can switch
   * off: a team that marked no grouping property gets `dimension: null` and the panel never
   * renders. Bundling it would make every overview pay for a query most projects skip.
   */
  async getFrontline(workspaceSlug: string, projectId: string): Promise<TProjectFrontline> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/frontline/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /** Overdue and urgent work items, capped at five. */
  async getAttention(workspaceSlug: string, projectId: string): Promise<TProjectAttention> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/attention/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * The project's milestones.
   *
   * Separate from `getOverview`, which embeds a summary with progress counts on it. This
   * is the manageable list: the shape you edit, with `work_item_count` so the UI knows
   * which ones the server will refuse to delete.
   */
  async listMilestones(workspaceSlug: string, projectId: string): Promise<TMilestone[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/milestones/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createMilestone(workspaceSlug: string, projectId: string, payload: TMilestonePayload): Promise<TMilestone> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/milestones/`, payload)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateMilestone(
    workspaceSlug: string,
    projectId: string,
    milestoneId: string,
    payload: Partial<TMilestonePayload>
  ): Promise<TMilestone> {
    return this.patch(`/api/workspaces/${workspaceSlug}/projects/${projectId}/milestones/${milestoneId}/`, payload)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteMilestone(workspaceSlug: string, projectId: string, milestoneId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/milestones/${milestoneId}/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createLink(
    workspaceSlug: string,
    projectId: string,
    payload: { url: string; title?: string }
  ): Promise<TProjectOverviewLink> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/links/`, payload)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteLink(workspaceSlug: string, projectId: string, linkId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/links/${linkId}/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Updates for one entity.
   *
   * `entityIdentifier` is optional because the project's own thread is the default: the
   * caller is already addressing the project in the path and should not have to restate it.
   */
  async listUpdates(
    workspaceSlug: string,
    projectId: string,
    entityName: TUpdateEntityName = "project",
    entityIdentifier?: string,
    labelId?: string
  ): Promise<TEntityUpdate[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/updates/`, {
      params: { entity_name: entityName, entity_identifier: entityIdentifier, label: labelId },
    })
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * One update's replies.
   *
   * Fetched on demand rather than shipped with the list: most updates are never expanded,
   * so loading every reply up front pays for a conversation nobody asked to read.
   */
  async listReplies(
    workspaceSlug: string,
    projectId: string,
    parentId: string,
    entityName: TUpdateEntityName = "project",
    entityIdentifier?: string
  ): Promise<TEntityUpdate[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/updates/`, {
      params: { entity_name: entityName, entity_identifier: entityIdentifier, parent: parentId },
    })
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createUpdate(workspaceSlug: string, projectId: string, payload: TEntityUpdatePayload): Promise<TEntityUpdate> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/updates/`, payload)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /** Rewriting an update, or refiling it under different topics. Author or admin only. */
  async updateUpdate(
    workspaceSlug: string,
    projectId: string,
    updateId: string,
    payload: Partial<TEntityUpdatePayload>
  ): Promise<TEntityUpdate> {
    return this.patch(`/api/workspaces/${workspaceSlug}/projects/${projectId}/updates/${updateId}/`, payload)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteUpdate(workspaceSlug: string, projectId: string, updateId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/updates/${updateId}/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
