/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Controller } from "react-hook-form";
import type { Control } from "react-hook-form";
import { Lock, Globe2 } from "lucide-react";
import { EViewAccess } from "@plane/types";

type Props = {
  control: Control<any>;
};

const OPTIONS = [
  { value: EViewAccess.PRIVATE, label: "Private", icon: Lock, hint: "Only you can see this view" },
  { value: EViewAccess.PUBLIC, label: "Public", icon: Globe2, hint: "Everyone in the project can see it" },
];

/**
 * Whether a saved view is private to its owner or visible to the project.
 *
 * `IssueView.access` has always existed and the list query has always honoured it --
 * `Q(owned_by=user) | Q(access=1)` hides other people's private views today. What was
 * missing was any way to set it: the field was `read_only` on the serializer, so every view
 * was created public and stayed there.
 */
export function AccessController({ control }: Props) {
  return (
    <Controller
      control={control}
      name="access"
      render={({ field: { value, onChange } }) => (
        <div className="flex items-center gap-1 rounded border border-subtle bg-surface-1 p-0.5">
          {OPTIONS.map((option) => {
            const Icon = option.icon;
            const selected = value === option.value;
            return (
              <button
                key={option.label}
                type="button"
                title={option.hint}
                aria-pressed={selected}
                onClick={() => onChange(option.value)}
                className={`flex h-7 items-center gap-1.5 rounded px-2 text-12 ${
                  selected ? "bg-surface-3 text-primary" : "text-tertiary hover:text-secondary"
                }`}
              >
                <Icon className="size-3.5" />
                {option.label}
              </button>
            );
          })}
        </div>
      )}
    />
  );
}
