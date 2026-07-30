/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { observer } from "mobx-react";
import { BLOCK_HEIGHT } from "@/components/gantt-chart/constants";
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useTimeLineChartStore } from "@/hooks/use-timeline-chart";

type Props = {
  blockIds?: string[];
  isEpic?: boolean;
};

/** Where a path leaves and enters a bar, and how far it stands off before turning. */
const ARROW = 6;
const ELBOW = 12;

/**
 * Blocked-by relations drawn between bars on the timeline.
 *
 * No schema was needed: `IssueRelation` with `IssueRelationChoices` has modelled this since
 * before the timeline existed, and the relation store already loads it for the detail panel.
 * What was missing was the geometry.
 *
 * Only `blocked_by` is drawn, and only in that direction. `blocking` is the same edge read
 * from the other end, so rendering both would double every line.
 */
export const TimelineDependencyPaths = observer(function TimelineDependencyPaths({ blockIds }: Props) {
  const { getBlockById } = useTimeLineChartStore();
  const { relation } = useIssueDetail();

  const paths = useMemo(() => {
    if (!blockIds?.length) return [];
    const rowOf = new Map(blockIds.map((id, index) => [id, index]));
    const centreY = (id: string) => (rowOf.get(id) ?? 0) * BLOCK_HEIGHT + BLOCK_HEIGHT / 2;

    const drawn: { key: string; d: string }[] = [];
    for (const blockedId of blockIds) {
      const blockedBy = relation.getRelationsByIssueId(blockedId)?.blocked_by ?? [];
      for (const blockerId of blockedBy) {
        // A relation whose other end is filtered out of this view has nothing to join to.
        if (!rowOf.has(blockerId)) continue;

        const blocker = getBlockById(blockerId);
        const blocked = getBlockById(blockedId);
        if (!blocker?.position || !blocked?.position) continue;

        const fromX = blocker.position.marginLeft + blocker.position.width;
        const toX = blocked.position.marginLeft;
        const fromY = centreY(blockerId);
        const toY = centreY(blockedId);

        // Right edge of the blocker, out, across at the blocked row, then in to its left
        // edge. When the blocked bar starts before the blocker ends the path has to go
        // around rather than backwards, so it stands off by a fixed elbow either way.
        const midX = toX - ELBOW > fromX + ELBOW ? (fromX + toX) / 2 : fromX + ELBOW;
        drawn.push({
          key: `${blockerId}-${blockedId}`,
          d: `M ${fromX} ${fromY} H ${midX} V ${toY} H ${toX - ARROW}`,
        });
      }
    }
    return drawn;
  }, [blockIds, getBlockById, relation]);

  if (!paths.length) return <></>;

  return (
    <svg className="pointer-events-none absolute top-0 left-0 h-full w-full overflow-visible" aria-hidden="true">
      <defs>
        <marker id="timeline-dependency-arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" className="fill-current text-tertiary" />
        </marker>
      </defs>
      {paths.map((path) => (
        <path
          key={path.key}
          d={path.d}
          fill="none"
          strokeWidth={1.5}
          className="stroke-current text-tertiary"
          markerEnd="url(#timeline-dependency-arrow)"
        />
      ))}
    </svg>
  );
});
