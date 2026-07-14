/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { useEffect, useState } from "react";
import { FlaskConical } from "lucide-react";
import { TestingService } from "@plane/services";
import type { TTestCase } from "@plane/types";

const testingService = new TestingService();

type Props = { workspaceSlug: string; projectId: string; issueId: string };

export function TestingWorkItemSummary({ workspaceSlug, projectId, issueId }: Props) {
  const [cases, setCases] = useState<TTestCase[]>();
  useEffect(() => {
    let active = true;
    void testingService
      .getWorkItemTestCases(workspaceSlug, projectId, issueId)
      .then((items) => active && setCases(items))
      .catch(() => active && setCases([]));
    return () => {
      active = false;
    };
  }, [issueId, projectId, workspaceSlug]);
  if (!cases?.length) return null;
  return (
    <section className="overflow-hidden rounded-lg border border-subtle bg-surface-1" aria-label="Testing coverage">
      <div className="flex items-center justify-between border-b border-subtle px-4 py-3">
        <div className="flex items-center gap-2">
          <FlaskConical className="size-4 text-accent-primary" />
          <h3 className="text-13 font-semibold text-primary">Testing coverage</h3>
        </div>
        <a
          href={`/${workspaceSlug}/projects/${projectId}/testing`}
          className="text-11 font-medium text-accent-primary hover:underline"
        >
          Open Testing
        </a>
      </div>
      {cases.map((testCase) => (
        <div
          key={testCase.id}
          className="grid grid-cols-[5rem_1fr_6rem] gap-3 border-b border-subtle px-4 py-3 text-12 last:border-0"
        >
          <span className="font-medium text-secondary">TC-{testCase.sequence}</span>
          <span className="text-primary">{testCase.current.title}</span>
          <span className="text-secondary capitalize">{testCase.latest_status ?? "Not run"}</span>
        </div>
      ))}
    </section>
  );
}
