/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { useMemo } from "react";
import type { TWorkItemProperty } from "@plane/types";
import { Checkbox, CustomSearchSelect } from "@plane/ui";
import { cn } from "@plane/utils";

type Props = {
  definition: TWorkItemProperty;
  value: unknown;
  onChange: (value: unknown) => void;
  onBlur?: () => void;
  disabled?: boolean;
  invalid?: boolean;
  className?: string;
};

const inputClass =
  "h-8 w-full rounded border border-subtle bg-surface-1 px-2 text-12 text-primary outline-none focus:border-accent-strong disabled:cursor-not-allowed disabled:opacity-60";

// Sentinel option that lets a single-select property go back to having no value.
const CLEAR_VALUE = "";

export function WorkItemPropertyField({ definition, value, onChange, onBlur, disabled, invalid, className }: Props) {
  const shared = {
    disabled,
    className: cn(inputClass, invalid && "border-danger-strong", className),
  };

  const isMultiSelect = definition.kind === "multi_select";
  const isOptionField = definition.kind === "select" || isMultiSelect;

  // Both kinds store option values; normalising to an array keeps the option list logic single-path.
  const selectedValues = useMemo(() => {
    if (isMultiSelect) return Array.isArray(value) ? value.map(String) : [];
    return typeof value === "string" && value ? [value] : [];
  }, [isMultiSelect, value]);

  const options = useMemo(() => {
    if (!isOptionField) return [];
    const optionList = definition.options.map((option) => ({
      value: option.value,
      query: option.label,
      content: isMultiSelect ? (
        <span className="flex items-center gap-2 truncate">
          <Checkbox checked={selectedValues.includes(option.value)} readOnly />
          <span className="truncate">{option.label}</span>
        </span>
      ) : (
        option.label
      ),
    }));
    if (isMultiSelect) return optionList;
    return [
      { value: CLEAR_VALUE, query: "no value", content: <span className="text-placeholder">No value</span> },
      ...optionList,
    ];
  }, [definition.options, isMultiSelect, isOptionField, selectedValues]);

  if (isOptionField) {
    const selectedLabels = definition.options
      .filter((option) => selectedValues.includes(option.value))
      .map((option) => option.label);
    const placeholder = isMultiSelect ? "Select options" : "Select an option";
    const dropdownProps = {
      className: "w-full",
      buttonClassName: cn(shared.className, "font-normal justify-between text-left"),
      label: (
        <span className={cn("truncate", selectedLabels.length === 0 && "text-placeholder")}>
          {selectedLabels.length > 0 ? selectedLabels.join(", ") : placeholder}
        </span>
      ),
      options,
      disabled,
      noResultsMessage: "No options found",
    };

    if (isMultiSelect)
      return (
        <CustomSearchSelect
          {...dropdownProps}
          multiple
          value={selectedValues}
          onChange={(next: string[]) => onChange(next)}
        />
      );

    return (
      <CustomSearchSelect
        {...dropdownProps}
        value={selectedValues[0] ?? CLEAR_VALUE}
        onChange={(next: string) => onChange(next || null)}
      />
    );
  }

  if (definition.kind === "boolean") {
    return (
      <select
        {...shared}
        value={value === true ? "true" : value === false ? "false" : ""}
        onChange={(event) => onChange(event.target.value === "" ? null : event.target.value === "true")}
        onBlur={onBlur}
      >
        <option value="">No value</option>
        <option value="true">True</option>
        <option value="false">False</option>
      </select>
    );
  }

  const stringValue = value === null || value === undefined ? "" : String(value);
  return (
    <input
      {...shared}
      type={
        definition.kind === "number"
          ? "number"
          : definition.kind === "date"
            ? "date"
            : definition.kind === "url"
              ? "url"
              : "text"
      }
      inputMode={definition.kind === "number" ? "decimal" : undefined}
      value={stringValue}
      placeholder={definition.description || definition.name}
      onBlur={onBlur}
      onChange={(event) => {
        if (definition.kind === "number") {
          onChange(event.target.value === "" ? null : Number(event.target.value));
          return;
        }
        onChange(event.target.value || null);
      }}
    />
  );
}
