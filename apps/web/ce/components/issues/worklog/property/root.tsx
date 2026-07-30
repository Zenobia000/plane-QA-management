/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useState } from "react";
import { Timer } from "lucide-react";
import { EnterpriseService } from "@plane/services";
import type { TWorklogSummary } from "@plane/types";

const service = new EnterpriseService();

type TIssueWorklogProperty = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  disabled: boolean;
};

/** Whole minutes rendered as hours and minutes, because that is how people read a duration. */
export const formatDuration = (minutes: number) => {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (!hours) return `${rest}m`;
  return rest ? `${hours}h ${rest}m` : `${hours}h`;
};

/**
 * Total time logged against this work item, in the property sidebar.
 *
 * A zero total renders nothing rather than "0m": a project that does not track time would
 * otherwise gain a permanent empty row in every work item's sidebar.
 */
export function IssueWorklogProperty({ workspaceSlug, projectId, issueId }: TIssueWorklogProperty) {
  const [summary, setSummary] = useState<TWorklogSummary | null>(null);

  const load = useCallback(async () => {
    try {
      setSummary(await service.worklogSummary(workspaceSlug, projectId, issueId));
    } catch {
      setSummary(null);
    }
  }, [workspaceSlug, projectId, issueId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!summary?.duration) return <></>;

  return (
    <div className="flex items-center gap-1.5 text-12 text-secondary" title="Time logged">
      <Timer className="size-3.5 text-tertiary" />
      {formatDuration(summary.duration)}
    </div>
  );
}
