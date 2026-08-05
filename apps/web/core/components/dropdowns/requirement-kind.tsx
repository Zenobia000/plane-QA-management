/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { useTranslation } from "@plane/i18n";
import type { TRequirementKind } from "@plane/types";
import { CustomSearchSelect } from "@plane/ui";
import { cn } from "@plane/utils";

type Props = {
  value: TRequirementKind | undefined | null;
  onChange: (value: TRequirementKind) => void;
  disabled?: boolean;
  className?: string;
  buttonClassName?: string;
};

/**
 * All three kinds are offered, `none` included and named.
 *
 * `none` is a real answer -- "this states no requirement", which is what a task implementing
 * one and a bug reporting one broken both are -- rather than the absence of an answer. A
 * "clear" affordance of the kind single-select custom properties get would say the opposite,
 * and the column cannot hold a null to mean it.
 */
export const REQUIREMENT_KIND_OPTIONS: TRequirementKind[] = ["none", "functional", "quality"];

export function RequirementKindDropdown({ value, onChange, disabled, className, buttonClassName }: Props) {
  const { t } = useTranslation();

  // Defaulted rather than left blank when the field is missing: the backend has no null for
  // it, so a work item loaded from an older cache is unclassified in the same sense as one
  // that was never classified.
  const selected: TRequirementKind = value ?? "none";

  const options = useMemo(
    () =>
      REQUIREMENT_KIND_OPTIONS.map((kind) => ({
        value: kind,
        query: t(`issue.requirement_kind.${kind}`),
        content: (
          <span className="flex flex-col">
            <span className="truncate">{t(`issue.requirement_kind.${kind}`)}</span>
            <span className="truncate text-11 text-secondary">{t(`issue.requirement_kind.${kind}_hint`)}</span>
          </span>
        ),
      })),
    [t]
  );

  return (
    <CustomSearchSelect
      value={selected}
      onChange={(next: TRequirementKind) => onChange(next)}
      options={options}
      disabled={disabled}
      className={cn("w-full", className)}
      buttonClassName={cn(
        "w-full justify-between border-none bg-transparent px-2 text-left text-body-xs-regular hover:bg-layer-2",
        buttonClassName
      )}
      label={<span className="truncate">{t(`issue.requirement_kind.${selected}`)}</span>}
      noResultsMessage={t("common.no_matching_results")}
      maxHeight="rg"
    />
  );
}
