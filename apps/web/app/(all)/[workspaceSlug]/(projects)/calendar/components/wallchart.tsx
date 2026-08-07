/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { observer } from "mobx-react";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { useParams } from "react-router";
import { useTranslation } from "@plane/i18n";
import type { TMemberLeave, TTeamEvent } from "@plane/types";
import { useAvailability } from "@/hooks/store/use-availability";
import { useMember } from "@/hooks/store/use-member";
import { browserZone, dateInZone, monthGrid, shiftMonth, spanCovers } from "../helpers";
import { ApprovalQueue } from "./approval-queue";
import { LeaveForm } from "./leave-form";

const HALF = new Set(["morning", "afternoon"]);

export const Wallchart = observer(function Wallchart() {
  const { t } = useTranslation();
  const { workspaceSlug } = useParams();
  const slug = workspaceSlug?.toString() ?? "";
  const { leaves, leaveTypes, events, fetchMonth, cancelLeave } = useAvailability();
  const {
    getUserDetails,
    workspace: { fetchWorkspaceMembers, workspaceMemberIds },
  } = useMember();

  // `toISOString()` is UTC, so on the first of the month before 08:00 in Taipei this opened
  // on the previous month. Everything else in this feature routes through `dateInZone`.
  const [month, setMonth] = useState(() => dateInZone(new Date(), browserZone()).slice(0, 7));
  const [composing, setComposing] = useState(false);

  const grid = useMemo(() => monthGrid(month), [month]);

  useEffect(() => {
    if (slug) void fetchWorkspaceMembers(slug);
  }, [fetchWorkspaceMembers, slug]);

  useEffect(() => {
    if (slug && grid.length) void fetchMonth(slug, grid[0], grid[grid.length - 1]);
  }, [fetchMonth, grid, slug]);

  const typeById = useMemo(() => Object.fromEntries(leaveTypes.map((type) => [type.id, type])), [leaveTypes]);
  const byMember = useMemo(() => {
    const map: Record<string, TMemberLeave[]> = {};
    for (const leave of leaves) (map[leave.member] ??= []).push(leave);
    return map;
  }, [leaves]);

  const members = workspaceMemberIds ?? Object.keys(byMember);

  const cellFor = (memberId: string, day: string) => {
    const leave = (byMember[memberId] ?? []).find((entry) => spanCovers(entry.start_date, entry.end_date, day));
    if (!leave) return null;
    const type = typeById[leave.leave_type];
    const half =
      (day === leave.start_date && HALF.has(leave.start_day_part)) ||
      (day === leave.end_date && HALF.has(leave.end_day_part));
    return { leave, colour: type?.colour ?? "#6B7280", half, name: type?.name ?? "" };
  };

  const eventsOn = (day: string): TTeamEvent[] =>
    events.filter((event) => spanCovers(event.start_date, event.end_date, day));

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setMonth(shiftMonth(month, -1))}
            className="rounded p-1 text-secondary hover:bg-surface-2"
            aria-label={t("team_calendar.wallchart.previous_month")}
          >
            <ChevronLeft className="size-4" />
          </button>
          <span className="text-13 text-secondary">{month}</span>
          <button
            type="button"
            onClick={() => setMonth(shiftMonth(month, 1))}
            className="rounded p-1 text-secondary hover:bg-surface-2"
            aria-label={t("team_calendar.wallchart.next_month")}
          >
            <ChevronRight className="size-4" />
          </button>
        </div>
        <button
          type="button"
          onClick={() => setComposing((open) => !open)}
          className="bg-accent-strong flex items-center gap-1.5 rounded px-3 py-1.5 text-13 text-white"
        >
          <Plus className="size-3.5" />
          {t("team_calendar.wallchart.log")}
        </button>
      </header>

      <ApprovalQueue />

      {composing && <LeaveForm onDone={() => setComposing(false)} />}

      <div className="overflow-x-auto rounded-lg border border-subtle">
        <table className="w-full border-collapse text-12">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-surface-1 p-2 text-left font-medium text-secondary">
                {t("team_calendar.wallchart.member")}
              </th>
              {grid.map((day) => (
                <th key={day} className="font-normal w-6 p-1 text-center text-tertiary">
                  {day.slice(8)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {members.map((memberId) => {
              const details = getUserDetails(memberId);
              return (
                <tr key={memberId} className="border-t border-subtle">
                  <td className="sticky left-0 z-10 max-w-40 truncate bg-surface-1 p-2 text-secondary">
                    {details?.display_name || details?.email || memberId}
                  </td>
                  {grid.map((day) => {
                    const cell = cellFor(memberId, day);
                    return (
                      <td key={day} className="p-0.5">
                        {cell && (
                          <button
                            type="button"
                            title={`${cell.name}${cell.half ? " (½)" : ""}`}
                            // Confirmed, because a block is the only thing in the grid that
                            // looks clickable and cancelling has no undo -- the API offers
                            // cancel/approve/reject and nothing that restores.
                            onClick={() => {
                              if (window.confirm(t("team_calendar.wallchart.confirm_cancel", { name: cell.name }))) {
                                void cancelLeave(slug, cell.leave.id);
                              }
                            }}
                            className="block h-4 w-full rounded-sm"
                            style={{
                              backgroundColor: cell.colour,
                              // A half day is drawn as half a block. Same information as a
                              // separate glyph, but it reads at a glance from across a row.
                              opacity: cell.leave.status === "pending" ? 0.45 : 1,
                              clipPath: cell.half ? "polygon(0 0, 100% 0, 0 100%)" : undefined,
                            }}
                          />
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
            {events.length > 0 && (
              <tr className="border-t-2 border-subtle">
                <td className="sticky left-0 z-10 bg-surface-1 p-2 font-medium text-secondary">
                  {t("team_calendar.wallchart.events")}
                </td>
                {grid.map((day) => {
                  const [event] = eventsOn(day);
                  return (
                    <td key={day} className="p-0.5">
                      {event && (
                        <span
                          title={event.title}
                          className="block h-4 w-full rounded-sm"
                          style={{ backgroundColor: event.colour }}
                        />
                      )}
                    </td>
                  );
                })}
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <ul className="flex flex-wrap gap-3 text-12 text-secondary">
        {leaveTypes.map((type) => (
          <li key={type.id} className="flex items-center gap-1.5">
            <span className="size-3 rounded-sm" style={{ backgroundColor: type.colour }} />
            {type.name}
            {!type.consumes_capacity && (
              <span className="text-tertiary">({t("team_calendar.wallchart.still_working")})</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
});
