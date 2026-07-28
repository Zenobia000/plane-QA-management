/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { useCallback, useMemo, useRef, useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { WorkItemExtensionService } from "@plane/services";
import type {
  ISearchIssueResponse,
  TIssue,
  TIssuePropertyValueErrors,
  TIssuePropertyValues,
  TProjectWorkItemType,
  TWorkItemProperty,
} from "@plane/types";
// components
import { IssueModalContext } from "@/components/issues/issue-modal/context";
import type { TIssueModalContext } from "@/components/issues/issue-modal/context";
// hooks
import { useUser } from "@/hooks/store/user/user-user";

export type TIssueModalProviderProps = {
  templateId?: string;
  dataForPreload?: Partial<TIssue>;
  allowedProjectIds?: string[];
  children: React.ReactNode;
};

export const IssueModalProvider = observer(function IssueModalProvider(props: TIssueModalProviderProps) {
  const { children, allowedProjectIds } = props;
  // states
  const [selectedParentIssue, setSelectedParentIssue] = useState<ISearchIssueResponse | null>(null);
  const [issuePropertyValues, setIssuePropertyValues] = useState<TIssuePropertyValues>({});
  const [issuePropertyValueErrors, setIssuePropertyValueErrors] = useState<TIssuePropertyValueErrors>({});
  const projectTypes = useRef<Record<string, TProjectWorkItemType[]>>({});
  const projectProperties = useRef<Record<string, TWorkItemProperty[]>>({});
  const service = useMemo(() => new WorkItemExtensionService(), []);
  // store hooks
  const { projectsWithCreatePermissions } = useUser();
  // derived values
  const projectIdsWithCreatePermissions = useMemo(
    () => Object.keys(projectsWithCreatePermissions ?? {}),
    [projectsWithCreatePermissions]
  );

  const handleProjectEntitiesFetch = useCallback(
    async ({
      workItemProjectId,
      workspaceSlug,
    }: {
      workItemProjectId: string | null | undefined;
      workspaceSlug: string;
    }) => {
      if (!workItemProjectId) return;
      const [types, properties] = await Promise.all([
        service.listProjectTypes(workspaceSlug, workItemProjectId),
        service.listProperties(workspaceSlug, workItemProjectId),
      ]);
      projectTypes.current[workItemProjectId] = types;
      projectProperties.current[workItemProjectId] = properties;
    },
    [service]
  );

  const handlePropertyValuesValidation = useCallback(
    ({ projectId }: { projectId: string | null }) => {
      if (!projectId) return true;
      const errors: TIssuePropertyValueErrors = {};
      for (const definition of projectProperties.current[projectId] ?? []) {
        const value = issuePropertyValues[definition.id];
        const empty =
          value === null || value === undefined || value === "" || (Array.isArray(value) && value.length === 0);
        if (definition.is_active && definition.is_required && empty && definition.default_value === null) {
          errors[definition.id] = "This property is required.";
        }
      }
      setIssuePropertyValueErrors(errors);
      return Object.keys(errors).length === 0;
    },
    [issuePropertyValues]
  );

  const handleCreateUpdatePropertyValues = useCallback(
    async ({
      issueId,
      projectId,
      workspaceSlug,
      isDraft,
    }: {
      issueId: string;
      projectId: string;
      workspaceSlug: string;
      isDraft?: boolean;
    }) => {
      if (isDraft) return;
      let definitions = projectProperties.current[projectId];
      if (!definitions) {
        definitions = await service.listProperties(workspaceSlug, projectId);
        projectProperties.current[projectId] = definitions;
      }
      await Promise.all(
        definitions
          .filter((definition) => definition.is_active)
          .map((definition) => {
            const value = issuePropertyValues[definition.id];
            const empty =
              value === null || value === undefined || value === "" || (Array.isArray(value) && value.length === 0);
            if (empty && !definition.is_required) {
              return service.clearPropertyValue(workspaceSlug, projectId, issueId, definition.id);
            }
            if (empty) return Promise.resolve();
            return service.setPropertyValue(workspaceSlug, projectId, issueId, definition.id, value);
          })
      );
      setIssuePropertyValues({});
      setIssuePropertyValueErrors({});
    },
    [issuePropertyValues, service]
  );

  const contextValue = useMemo<TIssueModalContext>(
    () => ({
      allowedProjectIds: allowedProjectIds ?? projectIdsWithCreatePermissions,
      workItemTemplateId: null,
      setWorkItemTemplateId: () => {},
      isApplyingTemplate: false,
      setIsApplyingTemplate: () => {},
      selectedParentIssue,
      setSelectedParentIssue,
      issuePropertyValues,
      setIssuePropertyValues,
      issuePropertyValueErrors,
      setIssuePropertyValueErrors,
      getIssueTypeIdOnProjectChange: (targetProjectId) =>
        projectTypes.current[targetProjectId]?.find((item) => item.is_default)?.type.id ??
        projectTypes.current[targetProjectId]?.[0]?.type.id ??
        null,
      getActiveAdditionalPropertiesLength: ({ projectId: targetProjectId }) =>
        targetProjectId
          ? (projectProperties.current[targetProjectId] ?? []).filter((item) => item.is_active).length
          : 0,
      handlePropertyValuesValidation,
      handleCreateUpdatePropertyValues,
      handleProjectEntitiesFetch,
      handleTemplateChange: async () => {},
      handleConvert: async () => {},
      handleCreateSubWorkItem: async () => {},
    }),
    [
      allowedProjectIds,
      handleCreateUpdatePropertyValues,
      handleProjectEntitiesFetch,
      handlePropertyValuesValidation,
      issuePropertyValueErrors,
      issuePropertyValues,
      projectIdsWithCreatePermissions,
      selectedParentIssue,
    ]
  );

  return <IssueModalContext.Provider value={contextValue}>{children}</IssueModalContext.Provider>;
});
