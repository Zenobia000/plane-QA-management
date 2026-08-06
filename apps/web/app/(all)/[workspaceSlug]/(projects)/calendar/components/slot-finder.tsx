/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { Search } from "lucide-react";
import { useParams } from "react-router";
import { useTranslation } from "@plane/i18n";
import type { TAvailabilityWindow, TMemberSchedule } from "@plane/types";
import { useAvailability } from "@/hooks/store/use-availability";
import { useMember } from "@/hooks/store/use-member";
import { clockInZone, dateInZone } from "../helpers";

const DURATIONS = [30, 60, 90, 120];

type Props = {
  days: string[];
  zone: string;
  members: TMemberSchedule[];
};

export const SlotFinder = observer(function SlotFinder({ days, zone, members }: Props) {
  const { t } = useTranslation();
  const { workspaceSlug } = useParams();
  const slug = workspaceSlug?.toString() ?? "";
  const { overlap, findOverlap, clearOverlap } = useAvailability();
  const { getUserDetails } = useMember();

  const [selected, setSelected] = useState<string[]>([]);
  const [duration, setDuration] = useState(60);
  const [searching, setSearching] = useState(false);

  const toggle = (memberId: string) =>
    setSelected((current) =>
      current.includes(memberId) ? current.filter((id) => id !== memberId) : [...current, memberId]
    );

  const search = async () => {
    if (selected.length === 0) return;
    setSearching(true);
    await findOverlap(slug, {
      member_ids: selected,
      date_from: days[0],
      date_to: days[6],
      duration_minutes: duration,
    });
    setSearching(false);
  };

  const name = (memberId: string) => {
    const details = getUserDetails(memberId);
    return details?.display_name || details?.email || memberId;
  };

  const renderWindows = (windows: TAvailabilityWindow[]) => (
    <ul className="flex flex-col gap-1">
      {windows.map((window) => (
        <li key={window.start} className="text-13 text-primary">
          <span className="text-secondary">{dateInZone(window.start, zone)}</span> {clockInZone(window.start, zone)}–
          {clockInZone(window.end, zone)} <span className="text-tertiary">({window.minutes} min)</span>
        </li>
      ))}
    </ul>
  );

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-subtle p-3">
      <h3 className="text-13 font-medium text-primary">{t("team_calendar.slot_finder.title")}</h3>

      <div className="flex flex-wrap gap-1">
        {members.map((entry) => (
          <button
            key={entry.member_id}
            type="button"
            onClick={() => toggle(entry.member_id)}
            className={`rounded-full px-2.5 py-1 text-12 ${
              selected.includes(entry.member_id)
                ? "bg-accent-strong text-white"
                : "hover:bg-surface-3 bg-surface-2 text-secondary"
            }`}
          >
            {name(entry.member_id)}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-13 text-secondary">
          {t("team_calendar.slot_finder.duration")}
          <select
            value={duration}
            onChange={(event) => setDuration(Number(event.target.value))}
            className="rounded border border-subtle bg-surface-1 px-2 py-1 text-13"
          >
            {DURATIONS.map((value) => (
              <option key={value} value={value}>
                {value} min
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={search}
          disabled={selected.length === 0 || searching}
          className="bg-accent-strong flex items-center gap-1.5 rounded px-3 py-1.5 text-13 text-white disabled:opacity-50"
        >
          <Search className="size-3.5" />
          {t("team_calendar.slot_finder.search")}
        </button>
        {overlap && (
          <button type="button" onClick={clearOverlap} className="text-13 text-secondary hover:text-primary">
            {t("team_calendar.slot_finder.clear")}
          </button>
        )}
      </div>

      {overlap && (
        <div className="flex flex-col gap-3">
          {overlap.members_without_hours.length > 0 && (
            // Named rather than quietly emptying the result: an empty answer with no
            // explanation reads as "never", when the truth is "someone hasn't said yet".
            <p className="text-12 text-warning-primary">
              {t("team_calendar.slot_finder.undeclared", {
                names: overlap.members_without_hours.map(name).join(", "),
              })}
            </p>
          )}

          <div>
            <h4 className="pb-1 text-12 font-medium text-secondary">{t("team_calendar.slot_finder.core")}</h4>
            {overlap.core.length > 0 ? (
              renderWindows(overlap.core)
            ) : (
              <p className="text-12 text-tertiary">{t("team_calendar.slot_finder.no_core")}</p>
            )}
          </div>

          <div>
            <h4 className="pb-1 text-12 font-medium text-secondary">{t("team_calendar.slot_finder.working")}</h4>
            {overlap.working.length > 0 ? (
              renderWindows(overlap.working)
            ) : (
              <p className="text-12 text-tertiary">{t("team_calendar.slot_finder.no_working")}</p>
            )}
          </div>
        </div>
      )}
    </section>
  );
});
