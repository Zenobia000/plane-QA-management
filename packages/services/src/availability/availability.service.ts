/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type {
  TAvailabilityCapabilities,
  TAvailabilitySchedule,
  TMemberWorkProfile,
  TMemberWorkProfileInput,
  TOverlapRequest,
  TOverlapResult,
  TUndeclaredWorkProfile,
  TWorkCalendar,
} from "@plane/types";
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

  private base(workspaceSlug: string) {
    return `/api/workspaces/${workspaceSlug}/availability`;
  }

  async getCapabilities(workspaceSlug: string): Promise<TAvailabilityCapabilities> {
    return this.get(`${this.base(workspaceSlug)}/capabilities/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getSchedule(
    workspaceSlug: string,
    from: string,
    to: string,
    memberIds?: string[]
  ): Promise<TAvailabilitySchedule> {
    return this.get(`${this.base(workspaceSlug)}/schedule/`, {
      params: { from, to, ...(memberIds?.length ? { member_ids: memberIds.join(",") } : {}) },
    })
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * POST for a read, deliberately: the member list is the request, and twenty UUIDs in a
   * query string is neither readable nor a length every proxy will carry. Nothing is written.
   */
  async findOverlap(workspaceSlug: string, payload: TOverlapRequest): Promise<TOverlapResult> {
    return this.post(`${this.base(workspaceSlug)}/overlap/`, payload)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getCalendars(workspaceSlug: string): Promise<TWorkCalendar[]> {
    return this.get(`${this.base(workspaceSlug)}/calendars/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getProfiles(workspaceSlug: string): Promise<TMemberWorkProfile[]> {
    return this.get(`${this.base(workspaceSlug)}/profiles/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateProfile(
    workspaceSlug: string,
    memberId: string,
    payload: TMemberWorkProfileInput
  ): Promise<TMemberWorkProfile | TUndeclaredWorkProfile> {
    return this.patch(`${this.base(workspaceSlug)}/profiles/${memberId}/`, payload)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
