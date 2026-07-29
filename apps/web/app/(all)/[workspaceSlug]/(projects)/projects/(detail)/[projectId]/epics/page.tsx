/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { useParams } from "react-router";
import { EpicService } from "@plane/services";
import type { TEpicHierarchy, TEpicNode } from "@plane/types";
import { PageHead } from "@/components/core/page-title";
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { TreeRow } from "./tree-row";

const epicService = new EpicService();

/**
 * The requirement hierarchy, which the work-item list cannot show.
 *
 * That list is a flat projection with `sub_issue` defaulting to true, so epic, feature and
 * story sit side by side in creation order. Turning the toggle off produces a tree, but the
 * parent rows stay uninformative: an epic's state is whatever someone set by hand, its
 * estimate is blank because points never sum upward, and nothing there says whether the
 * work beneath it has been verified.
 *
 * Every column here is therefore an aggregate over descendants, and the three chosen are the
 * three questions a delivery conversation actually asks: how far along, is it verified, how
 * big.
 */
export default function EpicsPage() {
  const { workspaceSlug, projectId } = useParams();
  const [hierarchy, setHierarchy] = useState<TEpicHierarchy | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { setPeekIssue } = useIssueDetail();

  useEffect(() => {
    if (!workspaceSlug || !projectId) return;
    let cancelled = false;
    epicService
      .getHierarchy(workspaceSlug.toString(), projectId.toString())
      .then((data) => {
        if (!cancelled) setHierarchy(data);
        return data;
      })
      .catch(() => {
        if (!cancelled) setError("Could not load the requirement hierarchy.");
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceSlug, projectId]);

  const openPeek = useCallback(
    (node: TEpicNode) => {
      if (!workspaceSlug || !projectId) return;
      setPeekIssue({
        workspaceSlug: workspaceSlug.toString(),
        projectId: projectId.toString(),
        issueId: node.id,
      });
    },
    [projectId, setPeekIssue, workspaceSlug]
  );

  const totals = useMemo(() => {
    const nodes = hierarchy?.nodes ?? [];
    return nodes.reduce(
      (sum, node) => ({
        items: sum.items + node.rollup.descendants + 1,
        points: sum.points + node.rollup.points.total,
        uncovered: sum.uncovered + (node.rollup.coverage.in_scope - node.rollup.coverage.covered),
      }),
      { items: 0, points: 0, uncovered: 0 }
    );
  }, [hierarchy]);

  if (!workspaceSlug || !projectId) return null;

  return (
    <>
      <PageHead title="Epics" />
      <main className="mx-auto flex h-full w-full max-w-6xl flex-col gap-4 p-6">
        <header className="flex flex-wrap items-baseline justify-between gap-3">
          <div>
            <h1 className="text-18 font-semibold text-primary">需求階層</h1>
            <p className="mt-0.5 text-12 text-tertiary">
              Epic → Feature → Story。每一列的數字都是底下所有後代的彙總,不是這一列自己的欄位。
            </p>
          </div>
          {hierarchy ? (
            <p className="text-12 text-secondary">
              {totals.items} 個需求 · {totals.points} 點
              {totals.uncovered ? (
                <span className="ml-2 font-medium text-danger-primary">{totals.uncovered} 個未覆蓋</span>
              ) : null}
            </p>
          ) : null}
        </header>

        {error ? (
          <div className="flex items-center gap-2 rounded border border-danger-subtle bg-danger-subtle px-3 py-2 text-13 text-danger-primary">
            <AlertTriangle className="size-4" />
            {error}
          </div>
        ) : null}

        {!hierarchy && !error ? <p className="text-13 text-tertiary">Loading…</p> : null}

        {hierarchy ? (
          <section className="rounded border border-subtle">
            <div className="grid grid-cols-[minmax(0,1fr)_9rem_7rem_5rem] gap-3 border-b border-subtle bg-layer-1 px-3 py-2 text-11 font-medium text-tertiary">
              <span>需求</span>
              <span>進度(底下的 story)</span>
              <span>驗收覆蓋</span>
              <span className="text-right">點數</span>
            </div>
            {hierarchy.nodes.length ? (
              hierarchy.nodes.map((node) => <TreeRow key={node.id} node={node} depth={0} onOpen={openPeek} />)
            ) : (
              <p className="px-3 py-6 text-center text-13 text-tertiary">
                尚未建立任何需求。建立 Epic 之後,底下的 Feature 與 Story 會在這裡成樹。
              </p>
            )}
          </section>
        ) : null}
      </main>
    </>
  );
}
