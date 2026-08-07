/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { useParams } from "react-router";
import { useAvailability } from "@/hooks/store/use-availability";
import { useUserPermissions } from "@/hooks/store/user";
import { CalendarSettings } from "./settings-calendars";
import { LeaveTypeSettings } from "./settings-leave-types";
import { MyHoursSettings } from "./settings-my-hours";

/**
 * Three sections, split by who owns the answer.
 *
 * My hours is a declaration the member makes about themself, so it is open to everyone and
 * comes first. Calendars and leave types are workspace policy, so they are admin-only and
 * read-only for everybody else — hidden entirely would leave a member unable to see why
 * their working days are what they are.
 */
export const SettingsView = observer(function SettingsView() {
  const { t } = useTranslation();
  const { workspaceSlug } = useParams();
  const slug = workspaceSlug?.toString() ?? "";
  const { fetchSettings, error } = useAvailability();
  const { allowPermissions } = useUserPermissions();

  const isAdmin = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.WORKSPACE);

  useEffect(() => {
    if (slug) void fetchSettings(slug);
  }, [fetchSettings, slug]);

  return (
    <div className="flex flex-col gap-8">
      {error && (
        <p className="rounded border border-danger-subtle bg-danger-subtle p-2 text-13 text-danger-primary">{error}</p>
      )}

      <MyHoursSettings />

      <section className="flex flex-col gap-3">
        <div>
          <h2 className="text-15 font-medium text-primary">{t("team_calendar.settings.calendars")}</h2>
          <p className="text-12 text-secondary">{t("team_calendar.settings.calendars_hint")}</p>
        </div>
        <CalendarSettings canEdit={isAdmin} />
      </section>

      <section className="flex flex-col gap-3">
        <div>
          <h2 className="text-15 font-medium text-primary">{t("team_calendar.settings.leave_types")}</h2>
          <p className="text-12 text-secondary">{t("team_calendar.settings.leave_types_hint")}</p>
        </div>
        <LeaveTypeSettings canEdit={isAdmin} />
      </section>
    </div>
  );
});
