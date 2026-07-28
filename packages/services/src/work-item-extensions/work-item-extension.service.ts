/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { API_BASE_URL } from "@plane/constants";
import type {
  TPaginatedWorkItemExtensionResponse,
  TProjectWorkItemType,
  TWorkItemProperty,
  TWorkItemPropertyValue,
  TWorkItemType,
} from "@plane/types";
import { APIService } from "../api.service";

type TListResponse<T> = T[] | TPaginatedWorkItemExtensionResponse<T>;

const results = <T>(payload: TListResponse<T>): T[] => (Array.isArray(payload) ? payload : payload.results);

export class WorkItemExtensionService extends APIService {
  constructor(BASE_URL?: string) {
    super(BASE_URL || API_BASE_URL);
  }

  async listWorkspaceTypes(workspaceSlug: string): Promise<TWorkItemType[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/work-item-types/`, { params: { per_page: 100 } })
      .then((response) => results<TWorkItemType>(response.data))
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createWorkspaceType(workspaceSlug: string, data: Partial<TWorkItemType>): Promise<TWorkItemType> {
    return this.post(`/api/workspaces/${workspaceSlug}/work-item-types/`, data)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateWorkspaceType(
    workspaceSlug: string,
    typeId: string,
    data: Partial<TWorkItemType>
  ): Promise<TWorkItemType> {
    return this.patch(`/api/workspaces/${workspaceSlug}/work-item-types/${typeId}/`, data)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteWorkspaceType(workspaceSlug: string, typeId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/work-item-types/${typeId}/`)
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async listProjectTypes(workspaceSlug: string, projectId: string): Promise<TProjectWorkItemType[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-types/`, {
      params: { per_page: 100 },
    })
      .then((response) => results<TProjectWorkItemType>(response.data))
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async enableProjectType(
    workspaceSlug: string,
    projectId: string,
    data: { type_id: string; level?: number; is_default?: boolean }
  ): Promise<TProjectWorkItemType> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-types/`, data)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateProjectType(
    workspaceSlug: string,
    projectId: string,
    projectTypeId: string,
    data: Partial<Pick<TProjectWorkItemType, "level" | "is_default">>
  ): Promise<TProjectWorkItemType> {
    return this.patch(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-types/${projectTypeId}/`, data)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async disableProjectType(workspaceSlug: string, projectId: string, projectTypeId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-types/${projectTypeId}/`)
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async listProperties(workspaceSlug: string, projectId: string): Promise<TWorkItemProperty[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-properties/`, {
      params: { per_page: 100 },
    })
      .then((response) => results<TWorkItemProperty>(response.data))
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createProperty(
    workspaceSlug: string,
    projectId: string,
    data: Partial<TWorkItemProperty>
  ): Promise<TWorkItemProperty> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-properties/`, data)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateProperty(
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    data: Partial<TWorkItemProperty>
  ): Promise<TWorkItemProperty> {
    return this.patch(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-properties/${propertyId}/`,
      data
    )
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteProperty(workspaceSlug: string, projectId: string, propertyId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-properties/${propertyId}/`)
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async listPropertyValues(
    workspaceSlug: string,
    projectId: string,
    issueId: string
  ): Promise<TWorkItemPropertyValue[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-items/${issueId}/properties/`, {
      params: { per_page: 100 },
    })
      .then((response) => results<TWorkItemPropertyValue>(response.data))
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async setPropertyValue(
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    propertyId: string,
    value: unknown
  ): Promise<TWorkItemPropertyValue> {
    return this.put(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/work-items/${issueId}/properties/${propertyId}/`,
      { value }
    )
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async clearPropertyValue(
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    propertyId: string
  ): Promise<void> {
    return this.delete(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/work-items/${issueId}/properties/${propertyId}/`
    )
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
