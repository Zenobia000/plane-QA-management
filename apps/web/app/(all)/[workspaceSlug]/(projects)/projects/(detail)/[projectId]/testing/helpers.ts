/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TTestCase } from "@plane/types";

export type TTestingTab = "overview" | "cases" | "runs";

/**
 * Test cases are addressed by their project-scoped sequence -- the TC-12 a
 * person reads on screen -- rather than by UUID, so URLs stay shareable.
 */
export const findCaseBySequence = (cases: Record<string, TTestCase>, sequence: string | undefined) => {
  if (!sequence || !/^\d+$/.test(sequence)) return undefined;
  const value = Number(sequence);
  return Object.values(cases).find((item) => item.sequence === value);
};

type TTestingPath = {
  workspaceSlug: string;
  projectId: string;
  tab?: TTestingTab;
  sequence?: number;
  runId?: string;
  runCaseId?: string;
  folderId?: string | null;
};

export const testingPath = ({ workspaceSlug, projectId, tab, sequence, runId, runCaseId, folderId }: TTestingPath) => {
  const segments = [`/${workspaceSlug}/projects/${projectId}/testing`];
  if (tab) segments.push(tab);
  if (tab === "cases" && sequence !== undefined) segments.push(String(sequence));
  // A run case is only addressable underneath its run; without one the deeper
  // segment would produce a route that cannot resolve.
  if (tab === "runs" && runId) {
    segments.push(runId);
    if (runCaseId) segments.push(runCaseId);
  }
  const path = segments.join("/");
  return folderId ? `${path}?folder=${folderId}` : path;
};
