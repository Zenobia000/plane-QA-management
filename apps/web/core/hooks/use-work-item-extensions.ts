/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import useSWR from "swr";
import { WorkItemExtensionService } from "@plane/services";

export const workItemExtensionService = new WorkItemExtensionService();

export const projectWorkItemTypesKey = (workspaceSlug?: string, projectId?: string) =>
  workspaceSlug && projectId ? `PROJECT_WORK_ITEM_TYPES_${workspaceSlug}_${projectId}` : null;

export const workspaceWorkItemTypesKey = (workspaceSlug?: string) =>
  workspaceSlug ? `WORKSPACE_WORK_ITEM_TYPES_${workspaceSlug}` : null;

export const workItemPropertiesKey = (workspaceSlug?: string, projectId?: string) =>
  workspaceSlug && projectId ? `WORK_ITEM_PROPERTIES_${workspaceSlug}_${projectId}` : null;

export const workItemPropertyValuesKey = (workspaceSlug?: string, projectId?: string, issueId?: string) =>
  workspaceSlug && projectId && issueId ? `WORK_ITEM_PROPERTY_VALUES_${workspaceSlug}_${projectId}_${issueId}` : null;

export const useProjectWorkItemTypes = (workspaceSlug?: string, projectId?: string) =>
  useSWR(projectWorkItemTypesKey(workspaceSlug, projectId), () =>
    workItemExtensionService.listProjectTypes(workspaceSlug!, projectId!)
  );

export const useWorkspaceWorkItemTypes = (workspaceSlug?: string) =>
  useSWR(workspaceWorkItemTypesKey(workspaceSlug), () => workItemExtensionService.listWorkspaceTypes(workspaceSlug!));

export const useWorkItemPropertyDefinitions = (workspaceSlug?: string, projectId?: string) =>
  useSWR(workItemPropertiesKey(workspaceSlug, projectId), () =>
    workItemExtensionService.listProperties(workspaceSlug!, projectId!)
  );

export const useWorkItemPropertyValues = (workspaceSlug?: string, projectId?: string, issueId?: string) =>
  useSWR(workItemPropertyValuesKey(workspaceSlug, projectId, issueId), () =>
    workItemExtensionService.listPropertyValues(workspaceSlug!, projectId!, issueId!)
  );
