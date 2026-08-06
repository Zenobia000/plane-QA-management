/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";
import { useParams } from "react-router";
import { useAvailability } from "@/hooks/store/use-availability";
import { useMember } from "@/hooks/store/use-member";
import { useUser } from "@/hooks/store/user";

/**
 * What the signed-in member declares about their own week.
 *
 * Only they may write it — a declaration somebody else made on your behalf is not a
 * declaration — so this form always edits the caller's own row and never offers a member
 * picker. An admin setting someone else's hours does it through the API, deliberately: it
 * should feel like an exception, because it is one.
 */
export const MyHoursSettings = observer(function MyHoursSettings() {
  const { t } = useTranslation();
  const { workspaceSlug } = useParams();
  const slug = workspaceSlug?.toString() ?? "";
  const { profiles, calendars, updateProfile, fetchSettings } = useAvailability();
  const { data: user } = useUser();
  const {
    workspace: { fetchWorkspaceMembers, workspaceMemberIds },
    getUserDetails,
  } = useMember();

  const memberId = user?.id ?? "";
  const mine = profiles[memberId];

  const [form, setForm] = useState({
    work_calendar: "",
    timezone: "",
    work_start_time: "09:00",
    work_end_time: "18:00",
    core_hours_start: "",
    core_hours_end: "",
    hours_per_day: "8",
    approver: "",
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (slug) void fetchWorkspaceMembers(slug);
  }, [fetchWorkspaceMembers, slug]);

  useEffect(() => {
    if (!mine) return;
    setForm({
      work_calendar: mine.work_calendar ?? "",
      timezone: mine.timezone ?? "",
      work_start_time: mine.work_start_time?.slice(0, 5) ?? "09:00",
      work_end_time: mine.work_end_time?.slice(0, 5) ?? "18:00",
      core_hours_start: mine.core_hours_start?.slice(0, 5) ?? "",
      core_hours_end: mine.core_hours_end?.slice(0, 5) ?? "",
      hours_per_day: mine.hours_per_day ?? "8",
      approver: mine.approver ?? "",
    });
  }, [mine]);

  const set = (key: keyof typeof form) => (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!memberId) return;
    setSaving(true);
    const clearing = !form.core_hours_start && !form.core_hours_end;
    try {
      await updateProfile(slug, memberId, {
        work_calendar: form.work_calendar || null,
        timezone: form.timezone || null,
        work_start_time: form.work_start_time,
        work_end_time: form.work_end_time,
        hours_per_day: form.hours_per_day,
        approver: form.approver || null,
        // Omitting a field means "leave it alone", so withdrawing a core-hours commitment
        // needs its own flag rather than two empty strings.
        ...(clearing
          ? { clear_core_hours: true }
          : { core_hours_start: form.core_hours_start, core_hours_end: form.core_hours_end }),
      });
      await fetchSettings(slug);
    } finally {
      setSaving(false);
    }
  };

  const colleagues = (workspaceMemberIds ?? []).filter((id) => id !== memberId);

  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2 className="text-15 font-medium text-primary">{t("team_calendar.settings.my_hours")}</h2>
        <p className="text-12 text-secondary">{t("team_calendar.settings.my_hours_hint")}</p>
      </div>

      <form onSubmit={save} className="flex flex-col gap-3 rounded-lg border border-subtle p-3">
        <div className="flex flex-wrap gap-3">
          <label className="flex flex-col gap-1 text-12 text-secondary">
            {t("team_calendar.settings.calendar")}
            <select
              value={form.work_calendar}
              onChange={set("work_calendar")}
              className="rounded border border-subtle bg-surface-1 px-2 py-1 text-13"
            >
              <option value="">{t("team_calendar.settings.use_default")}</option>
              {calendars.map((calendar) => (
                <option key={calendar.id} value={calendar.id}>
                  {calendar.name} ({calendar.timezone})
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-12 text-secondary">
            {t("team_calendar.settings.timezone_override")}
            <input
              type="text"
              value={form.timezone}
              onChange={set("timezone")}
              placeholder="Asia/Taipei"
              className="w-40 rounded border border-subtle bg-surface-1 px-2 py-1 text-13"
            />
          </label>

          <label className="flex flex-col gap-1 text-12 text-secondary">
            {t("team_calendar.settings.work_start")}
            <input
              type="time"
              value={form.work_start_time}
              onChange={set("work_start_time")}
              className="rounded border border-subtle bg-surface-1 px-2 py-1 text-13"
            />
          </label>

          <label className="flex flex-col gap-1 text-12 text-secondary">
            {t("team_calendar.settings.work_end")}
            <input
              type="time"
              value={form.work_end_time}
              onChange={set("work_end_time")}
              className="rounded border border-subtle bg-surface-1 px-2 py-1 text-13"
            />
          </label>

          <label className="flex flex-col gap-1 text-12 text-secondary">
            {t("team_calendar.settings.hours_per_day")}
            <input
              type="number"
              min={0.5}
              max={24}
              step={0.5}
              value={form.hours_per_day}
              onChange={set("hours_per_day")}
              className="w-20 rounded border border-subtle bg-surface-1 px-2 py-1 text-13"
            />
          </label>
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-12 text-secondary">
            {t("team_calendar.settings.core_start")}
            <input
              type="time"
              value={form.core_hours_start}
              onChange={set("core_hours_start")}
              className="rounded border border-subtle bg-surface-1 px-2 py-1 text-13"
            />
          </label>
          <label className="flex flex-col gap-1 text-12 text-secondary">
            {t("team_calendar.settings.core_end")}
            <input
              type="time"
              value={form.core_hours_end}
              onChange={set("core_hours_end")}
              className="rounded border border-subtle bg-surface-1 px-2 py-1 text-13"
            />
          </label>
          <p className="max-w-md pb-1 text-11 text-tertiary">{t("team_calendar.settings.core_hint")}</p>
        </div>

        <label className="flex flex-col gap-1 text-12 text-secondary">
          {t("team_calendar.settings.approver")}
          <select
            value={form.approver}
            onChange={set("approver")}
            className="w-64 rounded border border-subtle bg-surface-1 px-2 py-1 text-13"
          >
            <option value="">{t("team_calendar.settings.any_admin")}</option>
            {colleagues.map((id) => {
              const details = getUserDetails(id);
              return (
                <option key={id} value={id}>
                  {details?.display_name || details?.email || id}
                </option>
              );
            })}
          </select>
        </label>

        <div>
          <button
            type="submit"
            disabled={saving}
            className="bg-accent-strong rounded px-3 py-1.5 text-13 text-white disabled:opacity-50"
          >
            {t("team_calendar.settings.save")}
          </button>
        </div>
      </form>
    </section>
  );
});
