/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef } from "react";
import { WorkItemPropertyField } from "@/components/work-item-extensions";
import { useIssueModal } from "@/hooks/context/use-issue-modal";
import { useWorkItemPropertyDefinitions, useWorkItemPropertyValues } from "@/hooks/use-work-item-extensions";

export type TWorkItemModalAdditionalPropertiesProps = {
  isDraft?: boolean;
  projectId: string | null;
  workItemId: string | undefined;
  workspaceSlug: string;
};

export function WorkItemModalAdditionalProperties(props: TWorkItemModalAdditionalPropertiesProps) {
  const { isDraft = false, projectId, workItemId, workspaceSlug } = props;
  const {
    issuePropertyValues,
    setIssuePropertyValues,
    issuePropertyValueErrors,
    setIssuePropertyValueErrors,
    handleProjectEntitiesFetch,
  } = useIssueModal();
  const { data: definitions } = useWorkItemPropertyDefinitions(workspaceSlug, projectId ?? undefined);
  const { data: savedValues } = useWorkItemPropertyValues(
    workspaceSlug,
    projectId ?? undefined,
    isDraft ? undefined : workItemId
  );
  const loadedIssue = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (!projectId) return;
    void handleProjectEntitiesFetch({ workspaceSlug, workItemProjectId: projectId, workItemTypeId: undefined });
  }, [handleProjectEntitiesFetch, projectId, workspaceSlug]);

  useEffect(() => {
    if (!workItemId || !savedValues || loadedIssue.current === workItemId) return;
    setIssuePropertyValues(Object.fromEntries(savedValues.map((item) => [item.property.id, item.value])));
    loadedIssue.current = workItemId;
  }, [savedValues, setIssuePropertyValues, workItemId]);

  const activeDefinitions = definitions?.filter((item) => item.is_active) ?? [];
  if (!projectId || !activeDefinitions.length) return null;

  return (
    <section className="mt-4 border-t border-subtle pt-4">
      <h4 className="mb-3 text-12 font-medium text-secondary">Custom properties</h4>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {activeDefinitions.map((definition) => (
          <label key={definition.id} className="min-w-0">
            <span className="mb-1 block text-11 font-medium text-secondary">
              {definition.name}
              {definition.is_required && <span className="ml-0.5 text-danger-primary">*</span>}
            </span>
            <WorkItemPropertyField
              definition={definition}
              value={issuePropertyValues[definition.id] ?? definition.default_value}
              invalid={Boolean(issuePropertyValueErrors[definition.id])}
              onChange={(value) => {
                setIssuePropertyValues((current) => ({ ...current, [definition.id]: value }));
                setIssuePropertyValueErrors((current) => {
                  const next = { ...current };
                  delete next[definition.id];
                  return next;
                });
              }}
            />
            {Boolean(issuePropertyValueErrors[definition.id]) && (
              <span className="mt-1 block text-10 text-danger-primary">
                {String(issuePropertyValueErrors[definition.id])}
              </span>
            )}
          </label>
        ))}
      </div>
    </section>
  );
}
