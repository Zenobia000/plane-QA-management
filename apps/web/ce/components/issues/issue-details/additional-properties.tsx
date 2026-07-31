/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { useEffect, useState } from "react";
import { ListChecks } from "lucide-react";
import { propertiesForType, WorkItemPropertyField } from "@/components/work-item-extensions";
import { SidebarPropertyListItem } from "@/components/common/layout/sidebar/property-list-item";
import {
  useWorkItemPropertyDefinitions,
  useWorkItemPropertyValues,
  workItemExtensionService,
} from "@/hooks/use-work-item-extensions";

export type TWorkItemAdditionalSidebarProperties = {
  workItemId: string;
  workItemTypeId: string | null;
  projectId: string;
  workspaceSlug: string;
  isEditable: boolean;
  isPeekView?: boolean;
};

export function WorkItemAdditionalSidebarProperties(props: TWorkItemAdditionalSidebarProperties) {
  const { workItemId, workItemTypeId, projectId, workspaceSlug, isEditable } = props;
  const { data: definitions } = useWorkItemPropertyDefinitions(workspaceSlug, projectId);
  const { data: savedValues, mutate } = useWorkItemPropertyValues(workspaceSlug, projectId, workItemId);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    if (!savedValues) return;
    setValues(Object.fromEntries(savedValues.map((item) => [item.property.id, item.value])));
  }, [savedValues]);

  const saveValue = async (propertyId: string, value: unknown, required: boolean) => {
    const empty = value === null || value === undefined || value === "" || (Array.isArray(value) && value.length === 0);
    if (required && empty) {
      setErrors((current) => ({ ...current, [propertyId]: "This property is required." }));
      return;
    }
    setSaving(propertyId);
    setErrors((current) => ({ ...current, [propertyId]: "" }));
    try {
      if (empty) await workItemExtensionService.clearPropertyValue(workspaceSlug, projectId, workItemId, propertyId);
      else await workItemExtensionService.setPropertyValue(workspaceSlug, projectId, workItemId, propertyId, value);
      await mutate();
    } catch (error) {
      const message =
        error && typeof error === "object" && "error" in error ? String(error.error) : "Unable to save this property.";
      setErrors((current) => ({ ...current, [propertyId]: message }));
    } finally {
      setSaving(null);
    }
  };

  const activeDefinitions = propertiesForType(definitions, workItemTypeId);
  if (!activeDefinitions.length) return <></>;

  return (
    <div className="space-y-2.5 pt-1">
      {activeDefinitions.map((definition) => {
        const value = values[definition.id] ?? definition.default_value;
        const saveImmediately = ["boolean", "select", "multi_select", "date"].includes(definition.kind);
        return (
          <SidebarPropertyListItem
            key={definition.id}
            icon={ListChecks}
            label={`${definition.name}${definition.is_required ? " *" : ""}`}
          >
            <div className="w-full px-1">
              <WorkItemPropertyField
                definition={definition}
                value={value}
                disabled={!isEditable || saving === definition.id}
                invalid={Boolean(errors[definition.id])}
                className="h-7 border-0 bg-transparent px-1"
                onChange={(nextValue) => {
                  setValues((current) => ({ ...current, [definition.id]: nextValue }));
                  if (saveImmediately) void saveValue(definition.id, nextValue, definition.is_required);
                }}
                onBlur={() => {
                  if (!saveImmediately) void saveValue(definition.id, values[definition.id], definition.is_required);
                }}
              />
              {errors[definition.id] && <p className="px-1 text-10 text-danger-primary">{errors[definition.id]}</p>}
            </div>
          </SidebarPropertyListItem>
        );
      })}
    </div>
  );
}
