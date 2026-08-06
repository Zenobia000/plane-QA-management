/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import { AlertTriangle } from "lucide-react";
import { useParams } from "react-router";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";

import { useAvailability } from "@/hooks/store/use-availability";
import { useMember } from "@/hooks/store/use-member";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";

/**
 * People down, projects across.
 *
 * Members with no allocation are shown rather than filtered out: unallocated capacity is
 * exactly what someone planning a new piece of work is looking for, and a matrix that hides
 * it answers the wrong question.
 *
 * The total column is not a warning badge. The server refuses a write that would push
 * somebody past 100%, so a row can never sit at 120% — the number is there to be read while
 * deciding, not to be triaged afterwards.
 */
export const AllocationMatrix = observer(function AllocationMatrix() {
  const { t } = useTranslation();
  const { workspaceSlug } = useParams();
  const slug = workspaceSlug?.toString() ?? "";
  const { allocations, fetchAllocations, setAllocation, error } = useAvailability();
  const {
    getUserDetails,
    workspace: { fetchWorkspaceMembers, workspaceMemberIds },
  } = useMember();
  const { workspaceProjectIds, getProjectById } = useProject();
  const { allowPermissions } = useUserPermissions();

  const canEdit = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.WORKSPACE);

  useEffect(() => {
    if (slug) {
      void fetchWorkspaceMembers(slug);
      void fetchAllocations(slug);
    }
  }, [fetchAllocations, fetchWorkspaceMembers, slug]);

  const projects = workspaceProjectIds ?? [];
  const members = workspaceMemberIds ?? [];

  const percentFor = (memberId: string, projectId: string) =>
    allocations?.allocations.find((row) => row.member_id === memberId && row.project_id === projectId)
      ?.allocation_percent ?? 0;

  return (
    <section className="flex flex-col gap-3">
      <p className="text-12 text-secondary">
        {t("team_calendar.allocation.hint")} {!canEdit && t("team_calendar.allocation.admin_only")}
      </p>

      {error && <p className="text-12 text-danger-primary">{error}</p>}

      <div className="overflow-x-auto rounded-lg border border-subtle">
        <table className="w-full border-collapse text-13">
          <thead>
            <tr className="border-b border-subtle">
              <th className="p-2 text-left font-medium text-secondary">{t("team_calendar.allocation.member")}</th>
              {projects.map((projectId) => (
                <th key={projectId} className="p-2 text-left font-medium text-secondary">
                  {getProjectById?.(projectId)?.name ?? projectId}
                </th>
              ))}
              <th className="p-2 text-left font-medium text-secondary">{t("team_calendar.allocation.total")}</th>
            </tr>
          </thead>
          <tbody>
            {members.map((memberId) => {
              const details = getUserDetails(memberId);
              const total = allocations?.totals[memberId] ?? 0;
              return (
                <tr key={memberId} className="border-b border-subtle last:border-0">
                  <td className="max-w-48 truncate p-2 text-primary">
                    {details?.display_name || details?.email || memberId}
                  </td>
                  {projects.map((projectId) => (
                    <td key={projectId} className="p-1">
                      <input
                        type="number"
                        min={0}
                        max={100}
                        step={5}
                        disabled={!canEdit}
                        defaultValue={percentFor(memberId, projectId)}
                        onBlur={(event) => {
                          const next = Number(event.target.value);
                          if (next !== percentFor(memberId, projectId)) {
                            void setAllocation(slug, memberId, projectId, next);
                          }
                        }}
                        className="w-16 rounded border border-subtle bg-surface-1 px-2 py-1 text-13 disabled:opacity-60"
                      />
                    </td>
                  ))}
                  <td className="p-2">
                    <span className={total === 0 ? "text-tertiary" : "text-primary"}>{total}%</span>
                    {total === 0 && (
                      <span className="pl-2 text-11 text-tertiary">{t("team_calendar.allocation.unallocated")}</span>
                    )}
                    {total > 100 && (
                      <span className="inline-flex items-center gap-1 pl-2 text-11 text-danger-primary">
                        <AlertTriangle className="size-3" />
                        {t("team_calendar.allocation.over")}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
});
