/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { AlertTriangle } from "lucide-react";
import { AvailabilityService } from "@plane/services";
import { useTranslation } from "@plane/i18n";
import type { TCycleCapacity } from "@plane/types";
import { useMember } from "@/hooks/store/use-member";

const service = new AvailabilityService();

type Props = {
  workspaceSlug: string;
  projectId: string;
  cycleId: string;
};

/**
 * What this cycle actually has, after calendars, approved absence and allocation.
 *
 * Forward-looking only. It answers "does this fit" once, for this cycle; it never reports
 * hours worked and never accumulates per person across cycles — see ADR 0008.
 *
 * Fetched directly rather than through the availability store: that store is scoped to the
 * workspace-level calendar page, and a project sidebar borrowing its cache would make one
 * screen's staleness the other's problem.
 */
export const CycleCapacityPanel = observer(function CycleCapacityPanel({ workspaceSlug, projectId, cycleId }: Props) {
  const { t } = useTranslation();
  const { getUserDetails } = useMember();
  const [capacity, setCapacity] = useState<TCycleCapacity | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    service
      .getCycleCapacity(workspaceSlug, projectId, cycleId)
      .then((result) => live && setCapacity(result))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [workspaceSlug, projectId, cycleId]);

  if (failed || !capacity) return null;

  if (!capacity.ready) {
    return (
      <div className="border-t border-subtle py-4">
        <h4 className="pb-1 text-13 font-medium text-primary">{t("team_calendar.capacity.title")}</h4>
        <p className="text-12 text-tertiary">{t("team_calendar.capacity.no_dates")}</p>
      </div>
    );
  }

  const available = capacity.available_hours ?? 0;
  const committed = capacity.committed_hours ?? 0;
  const over = capacity.committed_comparable && committed > available;

  return (
    <div className="border-t border-subtle py-4">
      <h4 className="pb-2 text-13 font-medium text-primary">{t("team_calendar.capacity.title")}</h4>

      <table className="w-full text-12">
        <thead>
          <tr className="text-tertiary">
            <th className="font-normal pb-1 text-left">{t("team_calendar.capacity.member")}</th>
            <th className="font-normal pb-1 text-right">{t("team_calendar.capacity.allocation")}</th>
            <th className="font-normal pb-1 text-right">{t("team_calendar.capacity.absence")}</th>
            <th className="font-normal pb-1 text-right">{t("team_calendar.capacity.available")}</th>
          </tr>
        </thead>
        <tbody>
          {capacity.members.map((row) => {
            const details = getUserDetails(row.member_id);
            return (
              <tr key={row.member_id} className={row.declared ? "" : "text-tertiary"}>
                <td className="max-w-32 truncate py-0.5 text-secondary">
                  {details?.display_name || details?.email || row.member_id}
                </td>
                <td className="py-0.5 text-right text-secondary">{row.allocation_percent}%</td>
                <td className="py-0.5 text-right text-secondary">
                  {row.absence_hours ? `−${row.absence_hours}h` : "—"}
                </td>
                <td className="py-0.5 text-right text-primary">{row.available_hours}h</td>
              </tr>
            );
          })}
          <tr className="border-t border-subtle font-medium">
            <td className="py-1 text-secondary" colSpan={3}>
              {t("team_calendar.capacity.total")}
            </td>
            <td className="py-1 text-right text-primary">{available}h</td>
          </tr>
        </tbody>
      </table>

      {capacity.committed_comparable ? (
        <p className={`pt-2 text-12 ${over ? "text-danger-primary" : "text-secondary"}`}>
          {over && <AlertTriangle className="mr-1 inline size-3" />}
          {t("team_calendar.capacity.committed")}: {committed}h
          {over && ` · ${t("team_calendar.capacity.over", { hours: Math.round((committed - available) * 10) / 10 })}`}
        </p>
      ) : (
        // Deliberately says why rather than hiding the row: points and hours are not
        // commensurate, and a missing number with no explanation reads as a bug.
        <p className="pt-2 text-11 text-tertiary">{t("team_calendar.capacity.points_note")}</p>
      )}

      {capacity.allocation_is_assumed && (
        <p className="pt-1 text-11 text-tertiary">{t("team_calendar.capacity.assumed")}</p>
      )}
      {(capacity.undeclared_members?.length ?? 0) > 0 && (
        <p className="pt-1 text-11 text-tertiary">
          {t("team_calendar.capacity.undeclared", { count: capacity.undeclared_members?.length ?? 0 })}
        </p>
      )}
    </div>
  );
});
