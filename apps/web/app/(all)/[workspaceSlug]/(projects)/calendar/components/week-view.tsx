/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { observer } from "mobx-react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useParams } from "react-router";
import { useTranslation } from "@plane/i18n";
import type { TAvailabilityWindow, TMemberSchedule } from "@plane/types";
import { useAvailability } from "@/hooks/store/use-availability";
import { useMember } from "@/hooks/store/use-member";
import type { TBarPosition } from "../helpers";
import { addDays, barPosition, clockInZone, dateInZone, startOfDayInZone, weekOf } from "../helpers";
import { SlotFinder } from "./slot-finder";

const HOUR_TICKS = [0, 3, 6, 9, 12, 15, 18, 21];

const browserZone = () => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
};

type RowProps = {
  label: string;
  sublabel?: string;
  entry: Pick<TMemberSchedule, "working" | "core">;
  dayStart: Date;
  emphasis?: boolean;
};

/** Keeps each bar tied to the window it came from, so rows key on data rather than index. */
const placed = (windows: TAvailabilityWindow[], dayStart: Date) =>
  windows
    .map((window) => ({ window, position: barPosition(window, dayStart) }))
    .filter((entry): entry is { window: TAvailabilityWindow; position: TBarPosition } => entry.position !== null);

const ScheduleRow = ({ label, sublabel, entry, dayStart, emphasis }: RowProps) => {
  const { t } = useTranslation();
  const working = placed(entry.working, dayStart);
  const core = placed(entry.core, dayStart);

  return (
    <div className="flex items-center gap-3 py-1.5">
      <div className="w-40 shrink-0 truncate">
        <div className={`truncate text-13 ${emphasis ? "font-medium text-primary" : "text-secondary"}`}>{label}</div>
        {sublabel && <div className="truncate text-11 text-tertiary">{sublabel}</div>}
      </div>
      <div className="relative h-5 flex-1 rounded bg-surface-2">
        {working.length === 0 && (
          <span className="absolute inset-0 flex items-center pl-2 text-11 text-tertiary">
            {t("team_calendar.schedule.not_declared")}
          </span>
        )}
        {working.map(({ window, position }) => (
          <div
            key={`w-${window.start}`}
            className={`absolute inset-y-0 rounded ${emphasis ? "bg-accent-strong" : "bg-accent-subtle"}`}
            style={{ left: `${position.leftPercent}%`, width: `${position.widthPercent}%` }}
          />
        ))}
        {/* Drawn on top and darker: "I am at work" and "you may interrupt me" are two
            different claims, and one colour for both is how a calendar stops being trusted. */}
        {core.map(({ window, position }) => (
          <div
            key={`c-${window.start}`}
            className="bg-accent-strong absolute inset-y-0 rounded"
            style={{ left: `${position.leftPercent}%`, width: `${position.widthPercent}%` }}
            title="Core hours"
          />
        ))}
      </div>
    </div>
  );
};

export const WeekView = observer(function WeekView() {
  const { t } = useTranslation();
  const { workspaceSlug } = useParams();
  const slug = workspaceSlug?.toString() ?? "";
  const { schedule, scheduleLoading, fetchSchedule, capability } = useAvailability();
  const {
    getUserDetails,
    workspace: { fetchWorkspaceMembers },
  } = useMember();

  const [zone, setZone] = useState(browserZone);
  const [anchor, setAnchor] = useState(() => new Date());
  const [selectedDay, setSelectedDay] = useState<string | null>(null);

  const days = useMemo(() => weekOf(anchor, zone), [anchor, zone]);
  const day = selectedDay && days.includes(selectedDay) ? selectedDay : dateInZone(new Date(), zone);
  const activeDay = days.includes(day) ? day : days[0];
  const dayStart = useMemo(() => startOfDayInZone(activeDay, zone), [activeDay, zone]);

  useEffect(() => {
    if (slug) void fetchWorkspaceMembers(slug);
  }, [fetchWorkspaceMembers, slug]);

  useEffect(() => {
    // One request per week; the day chips only change which slice is drawn.
    if (slug) void fetchSchedule(slug, days[0], days[6]);
  }, [days, fetchSchedule, slug]);

  const members = useMemo(() => schedule?.members ?? [], [schedule]);
  const forDay = useMemo(
    () =>
      members.map((entry) => ({
        ...entry,
        working: entry.working.filter((w) => barPosition(w, dayStart)),
        core: entry.core.filter((w) => barPosition(w, dayStart)),
      })),
    [members, dayStart]
  );

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setAnchor(new Date(new Date(`${addDays(days[0], -7)}T12:00:00Z`)))}
            className="rounded p-1 text-secondary hover:bg-surface-2"
            aria-label={t("team_calendar.schedule.previous_week")}
          >
            <ChevronLeft className="size-4" />
          </button>
          <span className="text-13 text-secondary">
            {days[0]} – {days[6]}
          </span>
          <button
            type="button"
            onClick={() => setAnchor(new Date(new Date(`${addDays(days[0], 7)}T12:00:00Z`)))}
            className="rounded p-1 text-secondary hover:bg-surface-2"
            aria-label={t("team_calendar.schedule.next_week")}
          >
            <ChevronRight className="size-4" />
          </button>
        </div>
        <label className="flex items-center gap-2 text-13 text-secondary">
          {t("team_calendar.schedule.timezone")}
          <select
            value={zone}
            onChange={(event) => setZone(event.target.value)}
            className="rounded border border-subtle bg-surface-1 px-2 py-1 text-13"
          >
            {Array.from(new Set([browserZone(), "UTC", ...members.map((m) => m.timezone)])).map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      </header>

      <nav className="flex flex-wrap gap-1" aria-label={t("team_calendar.schedule.pick_day")}>
        {days.map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => setSelectedDay(value)}
            className={`rounded px-2.5 py-1 text-12 ${
              value === activeDay ? "bg-accent-strong text-white" : "hover:bg-surface-3 bg-surface-2 text-secondary"
            }`}
          >
            {value.slice(5)}
          </button>
        ))}
      </nav>

      <div className="rounded-lg border border-subtle p-3">
        <div className="flex items-center gap-3 pb-1">
          <div className="w-40 shrink-0" />
          <div className="relative h-4 flex-1">
            {HOUR_TICKS.map((hour) => (
              <span
                key={hour}
                className="absolute -translate-x-1/2 text-11 text-tertiary"
                style={{ left: `${(hour / 24) * 100}%` }}
              >
                {String(hour).padStart(2, "0")}
              </span>
            ))}
          </div>
        </div>

        {scheduleLoading && members.length === 0 ? (
          <div className="h-24 animate-pulse rounded bg-surface-2" aria-busy="true" />
        ) : (
          forDay.map((entry) => {
            const details = getUserDetails(entry.member_id);
            const hours = entry.working[0];
            return (
              <ScheduleRow
                key={entry.member_id}
                label={details?.display_name || details?.email || entry.member_id}
                sublabel={
                  hours
                    ? `${entry.timezone} · ${clockInZone(hours.start, zone)}–${clockInZone(hours.end, zone)}`
                    : entry.timezone
                }
                entry={entry}
                dayStart={dayStart}
              />
            );
          })
        )}
      </div>

      {capability?.capabilities.overlap && <SlotFinder days={days} zone={zone} members={members} />}
    </section>
  );
});
