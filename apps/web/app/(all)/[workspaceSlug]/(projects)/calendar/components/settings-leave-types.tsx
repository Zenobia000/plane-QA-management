/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { Plus } from "lucide-react";
import { useParams } from "react-router";
import { useTranslation } from "@plane/i18n";
import { useAvailability } from "@/hooks/store/use-availability";

type Props = { canEdit: boolean };

/**
 * Absence types.
 *
 * There is no delete, only an active switch. A type that has ever been used is part of the
 * record of who was away and why; removing it would rewrite that to tidy a settings list.
 * The server enforces this too — `MemberLeave.leave_type` is PROTECT.
 */
export const LeaveTypeSettings = observer(function LeaveTypeSettings({ canEdit }: Props) {
  const { t } = useTranslation();
  const { workspaceSlug } = useParams();
  const slug = workspaceSlug?.toString() ?? "";
  const { leaveTypes, createLeaveType, updateLeaveType } = useAvailability();

  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState({
    name: "",
    colour: "#6B7280",
    consumes_capacity: true,
    requires_approval: true,
  });

  return (
    <div className="flex flex-col gap-2">
      {leaveTypes.length === 0 && <p className="text-13 text-tertiary">{t("team_calendar.settings.no_types")}</p>}

      {leaveTypes.map((type) => (
        <div
          key={type.id}
          className={`flex flex-wrap items-center gap-3 rounded-lg border border-subtle p-3 ${
            type.is_active ? "" : "opacity-60"
          }`}
        >
          <input
            type="color"
            disabled={!canEdit}
            value={type.colour}
            onChange={(event) => void updateLeaveType(slug, type.id, { colour: event.target.value })}
            className="size-6 rounded border border-subtle"
            aria-label={t("team_calendar.settings.colour")}
          />
          <input
            type="text"
            disabled={!canEdit}
            defaultValue={type.name}
            onBlur={(event) => {
              if (event.target.value && event.target.value !== type.name) {
                void updateLeaveType(slug, type.id, { name: event.target.value });
              }
            }}
            className="w-40 rounded border border-subtle bg-surface-1 px-2 py-1 text-13 disabled:opacity-60"
          />

          <label className="flex items-center gap-1.5 text-12 text-secondary">
            <input
              type="checkbox"
              disabled={!canEdit}
              checked={type.consumes_capacity}
              onChange={(event) => void updateLeaveType(slug, type.id, { consumes_capacity: event.target.checked })}
            />
            {t("team_calendar.settings.consumes_capacity")}
          </label>

          <label className="flex items-center gap-1.5 text-12 text-secondary">
            <input
              type="checkbox"
              disabled={!canEdit}
              checked={type.requires_approval}
              onChange={(event) => void updateLeaveType(slug, type.id, { requires_approval: event.target.checked })}
            />
            {t("team_calendar.settings.requires_approval")}
          </label>

          <label className="ml-auto flex items-center gap-1.5 text-12 text-secondary">
            <input
              type="checkbox"
              disabled={!canEdit}
              checked={type.is_active}
              onChange={(event) => void updateLeaveType(slug, type.id, { is_active: event.target.checked })}
            />
            {t("team_calendar.settings.active")}
          </label>
        </div>
      ))}

      {canEdit &&
        (creating ? (
          <div className="flex flex-wrap items-center gap-2 rounded-lg border border-subtle p-3">
            <input
              type="color"
              value={draft.colour}
              onChange={(event) => setDraft({ ...draft, colour: event.target.value })}
              className="size-6 rounded border border-subtle"
              aria-label={t("team_calendar.settings.colour")}
            />
            <input
              type="text"
              value={draft.name}
              onChange={(event) => setDraft({ ...draft, name: event.target.value })}
              placeholder={t("team_calendar.settings.type_name")}
              className="w-40 rounded border border-subtle bg-surface-1 px-2 py-1 text-13"
            />
            <label className="flex items-center gap-1.5 text-12 text-secondary">
              <input
                type="checkbox"
                checked={draft.consumes_capacity}
                onChange={(event) => setDraft({ ...draft, consumes_capacity: event.target.checked })}
              />
              {t("team_calendar.settings.consumes_capacity")}
            </label>
            <label className="flex items-center gap-1.5 text-12 text-secondary">
              <input
                type="checkbox"
                checked={draft.requires_approval}
                onChange={(event) => setDraft({ ...draft, requires_approval: event.target.checked })}
              />
              {t("team_calendar.settings.requires_approval")}
            </label>
            <button
              type="button"
              onClick={async () => {
                if (!draft.name) return;
                // A duplicate name is refused by the server; closing the panel anyway would
                // report that refusal as a success.
                if (!(await createLeaveType(slug, draft))) return;
                setDraft({ name: "", colour: "#6B7280", consumes_capacity: true, requires_approval: true });
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
            {t("team_calendar.settings.new_type")}
          </button>
        ))}
    </div>
  );
});
