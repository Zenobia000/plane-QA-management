/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "react-router";
import { useTranslation } from "@plane/i18n";
import type { TDayPart } from "@plane/types";
import { useAvailability } from "@/hooks/store/use-availability";

type Props = { onDone: () => void };

/**
 * Logging an absence.
 *
 * There is deliberately no project selector. An absence belongs to the person, not to a
 * project — putting a project dropdown here would turn "I am away" into "I am away from
 * this project", which is not a thing anyone means. Allocation handles the split.
 */
export const LeaveForm = observer(function LeaveForm({ onDone }: Props) {
  const { t } = useTranslation();
  const { workspaceSlug } = useParams();
  const slug = workspaceSlug?.toString() ?? "";
  const { leaveTypes, createLeave, error } = useAvailability();

  const today = new Date().toISOString().slice(0, 10);
  const [typeId, setTypeId] = useState("");
  const [from, setFrom] = useState(today);
  const [to, setTo] = useState(today);
  const [part, setPart] = useState<TDayPart>("full");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);

  const single = from === to;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!typeId) return;
    setSaving(true);
    try {
      await createLeave(slug, {
        leave_type: typeId,
        start_date: from,
        end_date: to,
        // Half days only make sense on one day; a range is whole days at both ends.
        start_day_part: single ? part : "full",
        end_day_part: single ? part : "full",
        reason,
      });
      onDone();
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded-lg border border-subtle p-3">
      <div className="flex flex-wrap gap-3">
        <label className="flex flex-col gap-1 text-12 text-secondary">
          {t("team_calendar.form.type")}
          <select
            value={typeId}
            onChange={(event) => setTypeId(event.target.value)}
            required
            className="rounded border border-subtle bg-surface-1 px-2 py-1 text-13"
          >
            <option value="">—</option>
            {leaveTypes
              .filter((type) => type.is_active)
              .map((type) => (
                <option key={type.id} value={type.id}>
                  {type.name}
                </option>
              ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-12 text-secondary">
          {t("team_calendar.form.from")}
          <input
            type="date"
            value={from}
            onChange={(event) => {
              setFrom(event.target.value);
              if (event.target.value > to) setTo(event.target.value);
            }}
            className="rounded border border-subtle bg-surface-1 px-2 py-1 text-13"
          />
        </label>

        <label className="flex flex-col gap-1 text-12 text-secondary">
          {t("team_calendar.form.to")}
          <input
            type="date"
            value={to}
            min={from}
            onChange={(event) => setTo(event.target.value)}
            className="rounded border border-subtle bg-surface-1 px-2 py-1 text-13"
          />
        </label>

        {single && (
          <label className="flex flex-col gap-1 text-12 text-secondary">
            {t("team_calendar.form.part")}
            <select
              value={part}
              onChange={(event) => setPart(event.target.value as TDayPart)}
              className="rounded border border-subtle bg-surface-1 px-2 py-1 text-13"
            >
              <option value="full">{t("team_calendar.form.full_day")}</option>
              <option value="morning">{t("team_calendar.form.morning")}</option>
              <option value="afternoon">{t("team_calendar.form.afternoon")}</option>
            </select>
          </label>
        )}
      </div>

      <label className="flex flex-col gap-1 text-12 text-secondary">
        {t("team_calendar.form.reason")}
        <input
          type="text"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder={t("team_calendar.form.reason_hint")}
          className="rounded border border-subtle bg-surface-1 px-2 py-1 text-13"
        />
        <span className="text-11 text-tertiary">{t("team_calendar.form.reason_privacy")}</span>
      </label>

      {error && <p className="text-12 text-danger-primary">{error}</p>}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={saving || !typeId}
          className="bg-accent-strong rounded px-3 py-1.5 text-13 text-white disabled:opacity-50"
        >
          {t("team_calendar.form.submit")}
        </button>
        <button type="button" onClick={onDone} className="text-13 text-secondary hover:text-primary">
          {t("team_calendar.form.cancel")}
        </button>
      </div>
    </form>
  );
});
