/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { Users } from "lucide-react";
import { EnterpriseService } from "@plane/services";
import type { TTeamspace } from "@plane/types";

const service = new EnterpriseService();

export type TProjectTeamspaceList = {
  workspaceSlug: string;
  projectId: string;
};

/**
 * The teamspaces that cover this project.
 *
 * Filtered client-side from the workspace list rather than fetched per project: a workspace
 * has a handful of teamspaces, and a per-project endpoint would be a second way to ask a
 * question the list already answers.
 */
export function ProjectTeamspaceList({ workspaceSlug, projectId }: TProjectTeamspaceList) {
  const [teamspaces, setTeamspaces] = useState<TTeamspace[]>([]);

  useEffect(() => {
    let cancelled = false;
    service
      .listTeamspaces(workspaceSlug)
      .then((data) => {
        if (!cancelled) setTeamspaces(data.filter((team) => team.project_ids.includes(projectId)));
        return data;
      })
      .catch(() => setTeamspaces([]));
    return () => {
      cancelled = true;
    };
  }, [workspaceSlug, projectId]);

  if (!teamspaces.length) return null;

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {teamspaces.map((team) => (
        <span
          key={team.id}
          className="flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 text-11 text-secondary"
        >
          <Users className="size-3" />
          {team.name}
        </span>
      ))}
    </div>
  );
}
