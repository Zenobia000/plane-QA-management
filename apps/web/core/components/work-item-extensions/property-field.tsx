/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import type { ChangeEvent } from "react";
import type { TWorkItemProperty } from "@plane/types";
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

export function WorkItemPropertyField({ definition, value, onChange, onBlur, disabled, invalid, className }: Props) {
  const shared = {
    disabled,
    className: cn(inputClass, invalid && "border-danger-strong", className),
  };

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

  if (definition.kind === "select") {
    return (
      <select
        {...shared}
        value={typeof value === "string" ? value : ""}
        onChange={(event) => onChange(event.target.value || null)}
        onBlur={onBlur}
      >
        <option value="">Select an option</option>
        {definition.options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    );
  }

  if (definition.kind === "multi_select") {
    const selectedValues = Array.isArray(value) ? value.map(String) : [];
    return (
      <select
        {...shared}
        multiple
        value={selectedValues}
        onChange={(event: ChangeEvent<HTMLSelectElement>) =>
          onChange(Array.from(event.target.selectedOptions, (option) => option.value))
        }
        onBlur={onBlur}
        className={cn(shared.className, "h-auto min-h-20 py-1")}
      >
        {definition.options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
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
