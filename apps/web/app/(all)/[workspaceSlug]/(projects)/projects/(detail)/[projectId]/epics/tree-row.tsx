/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { ChevronRight } from "lucide-react";
import type { TEpicNode, TEpicStateGroup } from "@plane/types";

const STATE_ORDER: TEpicStateGroup[] = ["backlog", "unstarted", "started", "completed", "cancelled"];

const STATE_COLOR: Record<TEpicStateGroup, string> = {
  backlog: "bg-layer-3",
  unstarted: "bg-neutral-400",
  started: "bg-warning-solid",
  completed: "bg-success-solid",
  cancelled: "bg-danger-solid",
};

const STATUS_TONE: Record<string, string> = {
  failed: "bg-danger-subtle text-danger-primary",
  blocked: "bg-danger-subtle text-danger-primary",
  open: "bg-layer-2 text-secondary",
  skipped: "bg-layer-2 text-secondary",
  passed: "bg-success-subtle text-success-primary",
};

function StatusChip({ status }: { status: string | null }) {
  if (!status) return null;
  return (
    <span className={`rounded px-1.5 py-0.5 text-10 font-medium ${STATUS_TONE[status] ?? "bg-layer-2 text-secondary"}`}>
      {status}
    </span>
  );
}

/**
 * Progress over leaf descendants, as a proportional bar.
 *
 * A leaf has nothing beneath it, so it shows its own state instead of an empty bar. The
 * distinction matters: an empty bar would read as "no progress" when the honest statement
 * is "this is the work, not a summary of work".
 */
function ProgressCell({ node }: { node: TEpicNode }) {
  if (node.is_leaf) {
    return <span className="truncate text-11 text-secondary">{node.state ? node.state.name : "—"}</span>;
  }
  const distribution = node.rollup.state_distribution;
  const total = node.rollup.leaves;
  if (!total) return <span className="text-11 text-tertiary">—</span>;
  return (
    <div className="flex items-center gap-2">
      <div className="flex h-1.5 w-24 overflow-hidden rounded-full bg-layer-2">
        {STATE_ORDER.map((group) =>
          distribution[group] ? (
            <div
              key={group}
              className={STATE_COLOR[group]}
              style={{ width: `${(distribution[group] / total) * 100}%` }}
              title={`${group}: ${distribution[group]}`}
            />
          ) : null
        )}
      </div>
      <span className="shrink-0 text-11 text-tertiary">
        {distribution.completed}/{total}
      </span>
    </div>
  );
}

/** Coverage: a ratio over leaves for a parent, and a plain verdict for a leaf. */
function CoverageCell({ node }: { node: TEpicNode }) {
  if (node.is_leaf) {
    return (
      <div className="flex items-center gap-2">
        <span className={node.covered ? "text-11 text-secondary" : "text-11 font-medium text-danger-primary"}>
          {node.covered ? "已連結" : "無契約"}
        </span>
        <StatusChip status={node.latest_status} />
      </div>
    );
  }
  const { covered, in_scope: inScope, latest_status: status } = node.rollup.coverage;
  if (!inScope) return <span className="text-11 text-tertiary">—</span>;
  return (
    <div className="flex items-center gap-2">
      <span className={covered < inScope ? "text-11 font-medium text-danger-primary" : "text-11 text-secondary"}>
        {covered}/{inScope}
      </span>
      <StatusChip status={status} />
    </div>
  );
}

/** Points: the leaf's own estimate, or the sum of the leaves beneath. */
function PointsCell({ node }: { node: TEpicNode }) {
  if (node.is_leaf) {
    return <span className="text-right text-11 text-secondary">{node.estimate_point ?? "—"}</span>;
  }
  const { total, unsized } = node.rollup.points;
  return (
    <span className="text-right text-11 text-secondary">
      {total || "—"}
      {unsized ? (
        <span className="ml-1 text-tertiary" title={`${unsized} 個葉節點未估點`}>
          (+{unsized})
        </span>
      ) : null}
    </span>
  );
}

type TreeRowProps = {
  node: TEpicNode;
  depth: number;
  onOpen: (node: TEpicNode) => void;
};

export function TreeRow({ node, depth, onOpen }: TreeRowProps) {
  const [expanded, setExpanded] = useState(depth < 1);
  const hasChildren = node.children.length > 0;

  return (
    <>
      <div className="grid grid-cols-[minmax(0,1fr)_9rem_8rem_5rem] items-center gap-3 border-b border-subtle px-3 py-2 hover:bg-layer-1">
        <div className="flex min-w-0 items-center gap-1" style={{ paddingLeft: `${depth * 1.25}rem` }}>
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            className={`grid size-4 shrink-0 place-items-center rounded ${hasChildren ? "hover:bg-layer-2" : "invisible"}`}
            aria-label={expanded ? "Collapse" : "Expand"}
          >
            <ChevronRight className={`size-3 transition-transform ${expanded ? "rotate-90" : ""}`} />
          </button>
          {node.type ? (
            <span className="shrink-0 rounded bg-layer-2 px-1.5 py-0.5 text-10 font-medium text-secondary">
              {node.type.name}
            </span>
          ) : null}
          <button
            type="button"
            onClick={() => onOpen(node)}
            className="min-w-0 truncate text-13 text-primary hover:text-accent-primary hover:underline"
          >
            {node.name}
          </button>
          {node.rollup.leaves ? (
            <span className="shrink-0 text-11 text-tertiary" title="底下的葉節點數">
              {node.rollup.leaves}
            </span>
          ) : null}
        </div>
        <ProgressCell node={node} />
        <CoverageCell node={node} />
        <PointsCell node={node} />
      </div>
      {expanded
        ? node.children.map((child) => <TreeRow key={child.id} node={child} depth={depth + 1} onOpen={onOpen} />)
        : null}
    </>
  );
}
