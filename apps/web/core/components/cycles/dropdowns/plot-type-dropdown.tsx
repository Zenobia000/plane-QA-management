/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import { observer } from "mobx-react";
import type { TCyclePlotType } from "@plane/types";
import { CustomSelect } from "@plane/ui";
// local imports
import { cycleChartOptions } from "../analytics-sidebar/issue-progress";

type TProps = {
  value: TCyclePlotType;
  onChange: (value: TCyclePlotType) => void;
};

export const PlotTypeDropdown = observer(function PlotTypeDropdown(props: TProps) {
  const { value, onChange } = props;
  return (
    <div className="relative flex items-center gap-2">
      <CustomSelect
        value={value}
        label={<span>{cycleChartOptions.find((v) => v.value === value)?.label ?? "Burn-down"}</span>}
        onChange={onChange}
        maxHeight="lg"
        buttonClassName="bg-surface-2 border-none rounded-sm text-13 font-medium "
      >
        {cycleChartOptions.map((item) => (
          <CustomSelect.Option key={item.value} value={item.value}>
            {item.label}
          </CustomSelect.Option>
        ))}
      </CustomSelect>
    </div>
  );
});
