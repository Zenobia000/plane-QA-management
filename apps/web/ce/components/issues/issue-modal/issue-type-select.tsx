/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { useParams } from "react-router";
import type { Control, FieldPath } from "react-hook-form";
import { useController } from "react-hook-form";
// plane imports
import type { EditorRefApi } from "@plane/editor";
// types
import type { TBulkIssueProperties, TIssue } from "@plane/types";
import { WorkItemTypeBadge } from "@/components/work-item-extensions";
import { useProjectWorkItemTypes } from "@/hooks/use-work-item-extensions";

export type TIssueFields = TIssue & TBulkIssueProperties;

export type TIssueTypeDropdownVariant = "xs" | "sm";

export type TIssueTypeSelectProps<T extends Partial<TIssueFields>> = {
  control: Control<T>;
  projectId: string | null;
  editorRef?: React.MutableRefObject<EditorRefApi | null>;
  disabled?: boolean;
  variant?: TIssueTypeDropdownVariant;
  placeholder?: string;
  isRequired?: boolean;
  renderChevron?: boolean;
  dropDownContainerClassName?: string;
  showMandatoryFieldInfo?: boolean; // Show info about mandatory fields
  handleFormChange?: () => void;
};

export function IssueTypeSelect<T extends Partial<TIssueFields>>(props: TIssueTypeSelectProps<T>) {
  const {
    control,
    projectId,
    disabled = false,
    placeholder = "Work item type",
    isRequired = false,
    handleFormChange,
    dropDownContainerClassName,
    showMandatoryFieldInfo = false,
  } = props;
  const { workspaceSlug } = useParams();
  const slug = workspaceSlug?.toString();
  const { data: projectTypes, isLoading } = useProjectWorkItemTypes(slug, projectId ?? undefined);
  const { field, fieldState } = useController({
    control,
    name: "type_id" as FieldPath<T>,
    rules: { required: isRequired },
  });

  const defaultType = projectTypes?.find((item) => item.is_default) ?? projectTypes?.[0];

  useEffect(() => {
    if (!field.value && defaultType?.type.id) field.onChange(defaultType.type.id);
  }, [defaultType?.type.id, field]);

  const selectedType = projectTypes?.find((item) => item.type.id === field.value)?.type;

  return (
    <label
      className={`flex h-7 min-w-0 items-center rounded border bg-surface-1 px-1.5 ${
        fieldState.invalid ? "border-danger-strong" : "border-subtle"
      } ${dropDownContainerClassName ?? ""}`}
      title={showMandatoryFieldInfo && isRequired ? "This field is required" : selectedType?.description}
    >
      {selectedType && <WorkItemTypeBadge type={selectedType} compact className="mr-1 bg-transparent px-0" />}
      <select
        aria-label={placeholder}
        className="min-w-0 flex-1 bg-transparent text-12 text-primary outline-none"
        value={typeof field.value === "string" ? field.value : ""}
        onBlur={field.onBlur}
        onChange={(event) => {
          field.onChange(event.target.value || null);
          handleFormChange?.();
        }}
        disabled={disabled || isLoading || !projectTypes?.length}
      >
        <option value="">{isLoading ? "Loading types…" : placeholder}</option>
        {projectTypes?.map((item) => (
          <option key={item.id} value={item.type.id}>
            {item.type.name}
          </option>
        ))}
      </select>
    </label>
  );
}
