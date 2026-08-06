/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { Plus, Star, Trash2 } from "lucide-react";
import { useParams } from "react-router";
import { useTranslation } from "@plane/i18n";
import type { TCalendarDayKind } from "@plane/types";
import { useAvailability } from "@/hooks/store/use-availability";

const WEEKDAYS = [1, 2, 3, 4, 5, 6, 7];
const WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

type Props = { canEdit: boolean };

export const CalendarSettings = observer(function CalendarSettings({ canEdit }: Props) {
  const { t } = useTranslation();
  const { workspaceSlug } = useParams();
  const slug = workspaceSlug?.toString() ?? "";
  const {
    calendars,
    calendarDays,
    createCalendar,
    updateCalendar,
    deleteCalendar,
    fetchCalendarDays,
    addCalendarDays,
    removeCalendarDay,
  } = useAvailability();

  const [open, setOpen] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState({ name: "", timezone: "Asia/Taipei" });
  const [day, setDay] = useState({ date: "", name: "", kind: "holiday" as TCalendarDayKind });

  useEffect(() => {
    if (slug && open) void fetchCalendarDays(slug, open);
  }, [fetchCalendarDays, open, slug]);

  const toggleWeekday = (calendarId: string, current: number[], weekday: number) => {
    const next = current.includes(weekday)
      ? current.filter((value) => value !== weekday)
      : [...current, weekday].toSorted();
    // The server rejects an empty week; not sending it keeps the error out of the way of
    // someone mid-edit who unticked the last day before ticking another.
    if (next.length === 0) return;
    void updateCalendar(slug, calendarId, { working_weekdays: next });
  };

  const submitDay = async (calendarId: string) => {
    if (!day.date || !day.name) return;
    await addCalendarDays(slug, calendarId, [day]);
    setDay({ date: "", name: "", kind: "holiday" });
  };

  return (
    <div className="flex flex-col gap-3">
      {calendars.length === 0 && <p className="text-13 text-tertiary">{t("team_calendar.settings.no_calendars")}</p>}

      {calendars.map((calendar) => (
        <div key={calendar.id} className="rounded-lg border border-subtle">
          <div className="flex flex-wrap items-center gap-3 p-3">
            <button
              type="button"
              onClick={() => setOpen(open === calendar.id ? null : calendar.id)}
              className="text-13 font-medium text-primary"
            >
              {calendar.name}
            </button>
            <span className="text-12 text-tertiary">{calendar.timezone}</span>

            {calendar.is_default ? (
              <span className="text-accent-strong inline-flex items-center gap-1 text-11">
                <Star className="size-3" />
                {t("team_calendar.settings.default")}
              </span>
            ) : (
              canEdit && (
                <button
                  type="button"
                  onClick={() => void updateCalendar(slug, calendar.id, { is_default: true })}
                  className="text-11 text-secondary hover:text-primary"
                >
                  {t("team_calendar.settings.make_default")}
                </button>
              )
            )}

            <div className="flex gap-1">
              {WEEKDAYS.map((weekday) => (
                <button
                  key={weekday}
                  type="button"
                  disabled={!canEdit}
                  onClick={() => toggleWeekday(calendar.id, calendar.working_weekdays, weekday)}
                  className={`rounded px-1.5 py-0.5 text-11 ${
                    calendar.working_weekdays.includes(weekday)
                      ? "bg-accent-strong text-white"
                      : "bg-surface-2 text-tertiary"
                  } disabled:opacity-60`}
                >
                  {t(`team_calendar.settings.weekday.${WEEKDAY_KEYS[weekday - 1]}`)}
                </button>
              ))}
            </div>

            {canEdit && (
              <button
                type="button"
                onClick={() => void deleteCalendar(slug, calendar.id)}
                className="ml-auto text-secondary hover:text-danger-primary"
                aria-label={t("team_calendar.settings.delete_calendar")}
              >
                <Trash2 className="size-4" />
              </button>
            )}
          </div>

          {open === calendar.id && (
            <div className="border-t border-subtle p-3">
              <h4 className="pb-2 text-12 font-medium text-secondary">{t("team_calendar.settings.days")}</h4>

              <ul className="flex flex-col gap-1 pb-3">
                {(calendarDays[calendar.id] ?? []).map((entry) => (
                  <li key={entry.id} className="flex items-center gap-2 text-13">
                    <span className="w-24 text-secondary">{entry.date}</span>
                    <span className="text-primary">{entry.name}</span>
                    <span
                      className={`rounded px-1.5 py-0.5 text-11 ${
                        entry.kind === "makeup_workday"
                          ? "bg-warning-subtle text-warning-primary"
                          : "bg-surface-2 text-tertiary"
                      }`}
                    >
                      {t(`team_calendar.settings.kind.${entry.kind}`)}
                    </span>
                    {canEdit && (
                      <button
                        type="button"
                        onClick={() => void removeCalendarDay(slug, calendar.id, entry.id)}
                        className="text-tertiary hover:text-danger-primary"
                        aria-label={t("team_calendar.settings.remove_day")}
                      >
                        <Trash2 className="size-3" />
                      </button>
                    )}
                  </li>
                ))}
                {(calendarDays[calendar.id] ?? []).length === 0 && (
                  <li className="text-12 text-tertiary">{t("team_calendar.settings.no_days")}</li>
                )}
              </ul>

              {canEdit && (
                <div className="flex flex-wrap items-end gap-2">
                  <input
                    type="date"
                    value={day.date}
                    onChange={(event) => setDay({ ...day, date: event.target.value })}
                    className="rounded border border-subtle bg-surface-1 px-2 py-1 text-13"
                  />
                  <input
                    type="text"
                    value={day.name}
                    onChange={(event) => setDay({ ...day, name: event.target.value })}
                    placeholder={t("team_calendar.settings.day_name")}
                    className="rounded border border-subtle bg-surface-1 px-2 py-1 text-13"
                  />
                  <select
                    value={day.kind}
                    onChange={(event) => setDay({ ...day, kind: event.target.value as TCalendarDayKind })}
                    className="rounded border border-subtle bg-surface-1 px-2 py-1 text-13"
                  >
                    <option value="holiday">{t("team_calendar.settings.kind.holiday")}</option>
                    {/* The reason this whole screen exists: a Saturday everyone works cannot
                        be expressed by a weekday mask, and until now could only be seeded. */}
                    <option value="makeup_workday">{t("team_calendar.settings.kind.makeup_workday")}</option>
                  </select>
                  <button
                    type="button"
                    onClick={() => void submitDay(calendar.id)}
                    className="bg-accent-strong rounded px-3 py-1.5 text-13 text-white"
                  >
                    {t("team_calendar.settings.add_day")}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      ))}

      {canEdit &&
        (creating ? (
          <div className="flex flex-wrap items-end gap-2 rounded-lg border border-subtle p-3">
            <input
              type="text"
              value={draft.name}
              onChange={(event) => setDraft({ ...draft, name: event.target.value })}
              placeholder={t("team_calendar.settings.calendar_name")}
              className="rounded border border-subtle bg-surface-1 px-2 py-1 text-13"
            />
            <input
              type="text"
              value={draft.timezone}
              onChange={(event) => setDraft({ ...draft, timezone: event.target.value })}
              placeholder="Asia/Taipei"
              className="rounded border border-subtle bg-surface-1 px-2 py-1 text-13"
            />
            <button
              type="button"
              onClick={async () => {
                if (!draft.name) return;
                await createCalendar(slug, { ...draft, is_default: calendars.length === 0 });
                setDraft({ name: "", timezone: "Asia/Taipei" });
                setCreating(false);
              }}
              className="bg-accent-strong rounded px-3 py-1.5 text-13 text-white"
            >
              {t("team_calendar.settings.create")}
            </button>
            <button
              type="button"
              onClick={() => setCreating(false)}
              className="text-13 text-secondary hover:text-primary"
            >
              {t("team_calendar.form.cancel")}
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="flex w-fit items-center gap-1.5 rounded border border-subtle px-3 py-1.5 text-13 text-secondary hover:text-primary"
          >
            <Plus className="size-3.5" />
            {t("team_calendar.settings.new_calendar")}
          </button>
        ))}
    </div>
  );
});
