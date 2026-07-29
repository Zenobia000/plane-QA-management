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
 * Every column here is therefore an aggregate over the node's *leaf* descendants, answering
 * the three questions a delivery conversation asks: how far along, is it verified, how big.
 *
 * Leaves rather than all descendants, because a feature's state is a hand-set summary of the
 * same stories it contains -- counting both states one fact twice. A leaf row shows its own
 * values instead, since it has nothing beneath it to summarise.
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

  /**
   * Walked rather than summed from the roots, because a root may itself be a leaf and a
   * leaf's rollup is empty by construction -- its figures live on the node.
   */
  const totals = useMemo(() => {
    let items = 0;
    let points = 0;
    let uncovered = 0;
    const visit = (node: TEpicNode) => {
      items += 1;
      if (node.is_leaf) {
        points += node.estimate_point ?? 0;
        if (!node.covered) uncovered += 1;
      }
      node.children.forEach(visit);
    };
    (hierarchy?.nodes ?? []).forEach(visit);
    return { items, points, uncovered };
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
              Epic → Feature → Story。父層的數字只統計底下的葉節點 —— 中間層是摘要,計入會把同一份工作數兩次。
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
            <div className="grid grid-cols-[minmax(0,1fr)_9rem_8rem_5rem] gap-3 border-b border-subtle bg-layer-1 px-3 py-2 text-11 font-medium text-tertiary">
              <span>需求</span>
              <span title="只計葉節點:中間層是摘要,計入會重複計算">進度(葉節點)</span>
              <span title="已連結驗收契約的葉節點比例">驗收覆蓋</span>
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
