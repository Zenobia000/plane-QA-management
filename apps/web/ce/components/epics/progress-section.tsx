/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
// plane imports
import { STATE_GROUPS } from "@plane/constants";
import { EpicService } from "@plane/services";
import type { TEpicAnalyticsGroup, TStateGroups } from "@plane/types";
import { LinearProgressIndicator } from "@plane/ui";

const epicService = new EpicService();

type Props = {
  workspaceSlug: string;
  projectId: string;
  epicId: string;
};

/**
 * The order the bar reads left to right: not yet picked up, through to finished.
 *
 * Cancelled sits last and is counted, not hidden. Dropping it from the denominator would
 * make a mostly-cancelled epic read as nearly complete, and dropping it from the display
 * would leave the numbers not adding up to the work that exists.
 */
const GROUP_ORDER: { group: TStateGroups; key: TEpicAnalyticsGroup }[] = [
  { group: "backlog", key: "backlog_issues" },
  { group: "unstarted", key: "unstarted_issues" },
  { group: "started", key: "started_issues" },
  { group: "completed", key: "completed_issues" },
  { group: "cancelled", key: "cancelled_issues" },
];

/**
 * How the work beneath an epic is distributed, which the epic's own row cannot say.
 *
 * An epic's state is set by hand and its estimate is usually blank, so the only honest
 * answer to "how is this going" is an aggregate over its descendants. That aggregate is
 * computed server-side -- see `EpicAnalyticsEndpoint` -- because it walks the whole subtree
 * and the client holds only the rows it has paged in.
 */
export const EpicProgressSection = observer(function EpicProgressSection(props: Props) {
  const { workspaceSlug, projectId, epicId } = props;

  const { data, isLoading } = useSWR(
    workspaceSlug && projectId && epicId ? `EPIC_ANALYTICS_${workspaceSlug}_${projectId}_${epicId}` : null,
    workspaceSlug && projectId && epicId ? () => epicService.getAnalytics(workspaceSlug, projectId, epicId) : null,
    { revalidateOnFocus: false }
  );

  const { total, bars } = useMemo(() => {
    if (!data) return { total: 0, bars: [] };
    const barData = GROUP_ORDER.map(({ group, key }) => ({
      id: group,
      name: STATE_GROUPS[group].label,
      value: data[key],
      color: STATE_GROUPS[group].color,
    }));
    return { total: barData.reduce((sum, item) => sum + item.value, 0), bars: barData };
  }, [data]);

  // Nothing beneath the epic yet. A zeroed bar would read as "no progress" rather than
  // "nothing to report", so the section stays out of the way until there is work.
  if (isLoading || !data || total === 0) return null;

  return (
    <div className="flex flex-col gap-3 py-3">
      <div className="flex items-center justify-between">
        <h5 className="text-13 font-medium text-secondary">Progress</h5>
        <span className="text-13 text-tertiary">
          {data.completed_issues} of {total} done
        </span>
      </div>
      <LinearProgressIndicator size="lg" data={bars} />
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
        {bars
          .filter((item) => item.value > 0)
          .map((item) => (
            <div key={item.id} className="flex items-center gap-1.5">
              <span className="h-2 w-2 flex-shrink-0 rounded-full" style={{ backgroundColor: item.color }} />
              <span className="text-11 text-tertiary">
                {item.name} {item.value}
              </span>
            </div>
          ))}
        {data.overdue_issues > 0 && (
          <span className="text-danger text-11 font-medium">{data.overdue_issues} overdue</span>
        )}
      </div>
    </div>
  );
});
