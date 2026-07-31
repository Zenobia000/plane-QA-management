/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
// plane imports
import { AreaChart } from "@plane/propel/charts/area-chart";
import type { TAreaItem, TChartData, TCyclePlotType, TModuleCompletionChartDistribution } from "@plane/types";
import { renderFormattedDateWithoutYear } from "@plane/utils";

type Props = {
  distribution: TModuleCompletionChartDistribution;
  totalIssues: number;
  className?: string;
  plotTitle?: string;
  plotType?: TCyclePlotType;
};

function ProgressChart({
  distribution,
  totalIssues,
  className = "",
  plotTitle = "work items",
  plotType = "burndown",
}: Props) {
  const isBurnUp = plotType === "burnup";
  const dates = Object.keys(distribution ?? {});
  const lastIndex = dates.length - 1;

  const chartData: TChartData<string, string>[] = dates.map((key, index) => {
    // The API sends null for dates past today. Keep them null so the line stops at
    // today — coercing to 0 would draw the remaining work as if it had all landed.
    const pending = distribution[key];
    const hasData = pending !== null && pending !== undefined;
    // Ratio of the cycle elapsed at this point, used to draw the ideal trend line.
    const elapsed = lastIndex > 0 ? index / lastIndex : 1;

    return Object.assign(
      {
        name: renderFormattedDateWithoutYear(key),
        current: hasData ? (isBurnUp ? totalIssues - pending : pending) : null,
        ideal: totalIssues * (isBurnUp ? elapsed : 1 - elapsed),
      },
      isBurnUp ? { scope: totalIssues } : {}
    );
  });

  const areas: TAreaItem<string>[] = [
    {
      key: "current",
      label: isBurnUp ? `Completed ${plotTitle}` : `Current ${plotTitle}`,
      strokeColor: "#3F76FF",
      fill: "#3F76FF33",
      fillOpacity: 1,
      showDot: true,
      smoothCurves: true,
      strokeOpacity: 1,
    },
    {
      key: "ideal",
      label: `Ideal ${plotTitle}`,
      strokeColor: "#A9BBD0",
      fill: "#A9BBD0",
      fillOpacity: 0,
      showDot: true,
      smoothCurves: true,
      strokeOpacity: 1,
      style: {
        strokeDasharray: "6, 3",
        strokeWidth: 1,
      },
    },
  ];

  if (isBurnUp) {
    areas.push({
      key: "scope",
      label: `Total ${plotTitle}`,
      strokeColor: "#E5A343",
      fill: "#E5A343",
      fillOpacity: 0,
      showDot: false,
      smoothCurves: false,
      strokeOpacity: 1,
      style: {
        strokeDasharray: "2, 2",
        strokeWidth: 1,
      },
    });
  }

  return (
    <div className={`flex w-full items-center justify-center ${className}`}>
      <AreaChart
        data={chartData}
        areas={areas}
        xAxis={{ key: "name", label: "Date" }}
        yAxis={{ key: "current", label: "Completion" }}
        margin={{ bottom: 30 }}
        className="h-[370px] w-full"
        legend={{
          align: "center",
          verticalAlign: "bottom",
          layout: "horizontal",
          wrapperStyles: {
            marginTop: 20,
          },
        }}
      />
    </div>
  );
}

export default ProgressChart;
