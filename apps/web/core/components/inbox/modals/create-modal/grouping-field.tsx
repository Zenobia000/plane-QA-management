/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TWorkItemProperty } from "@plane/types";
// components
import { WorkItemPropertyField } from "@/components/work-item-extensions";

type TIntakeGroupingFieldProps = {
  definition: TWorkItemProperty | undefined;
  error?: string;
  onChange: (value: unknown) => void;
  tabIndex?: number;
  value: unknown;
};

/**
 * The "whose is this" question on the intake form.
 *
 * Deliberately the only custom property the form asks for. A reporter filing something
 * from outside the team knows which account it came from and nothing about the project's
 * other fields, so asking for the rest here would be asking someone to guess. The
 * remainder are filled by whoever triages the item, in the intake detail panel.
 *
 * The heading is the property's own name, because no category name is compiled into this
 * product -- one project reads 合作客戶, the next reads Region.
 */
export function IntakeGroupingField(props: TIntakeGroupingFieldProps) {
  const { definition, error, onChange, tabIndex, value } = props;
  if (!definition) return null;

  return (
    <div className="min-w-0" tabIndex={tabIndex}>
      <span className="mb-1 block text-11 font-medium text-secondary">
        {definition.name}
        {definition.is_required && <span className="ml-0.5 text-danger-primary">*</span>}
      </span>
      <WorkItemPropertyField
        definition={definition}
        value={value}
        invalid={Boolean(error)}
        onChange={onChange}
        className="bg-layer-2"
      />
      {error && <span className="mt-1 block text-10 text-danger-primary">{error}</span>}
    </div>
  );
}
