/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import { AlertTriangle } from "lucide-react";
import { NavLink, Outlet, useParams } from "react-router";
import { useTranslation } from "@plane/i18n";
import { PageHead } from "@/components/core/page-title";
import { useAvailability } from "@/hooks/store/use-availability";
import { AVAILABILITY_TABS, availabilityPath } from "./helpers";

function TeamCalendarPage() {
  const { t } = useTranslation();
  const { workspaceSlug } = useParams();
  const { error, fetchCapabilities } = useAvailability();

  useEffect(() => {
    if (workspaceSlug) void fetchCapabilities(workspaceSlug);
  }, [fetchCapabilities, workspaceSlug]);

  if (!workspaceSlug) return null;

  return (
    <>
      <PageHead title={t("team_calendar.title")} />
      <main className="mx-auto flex h-full w-full max-w-6xl flex-col gap-5 p-6">
        <nav className="flex gap-1 border-b border-subtle" aria-label={t("team_calendar.title")}>
          {AVAILABILITY_TABS.map((tab) => (
            <NavLink
              key={tab}
              to={availabilityPath({ workspaceSlug, tab })}
              className={({ isActive }) =>
                `border-b-2 px-3 py-2 text-13 font-medium ${
                  isActive ? "border-accent-strong text-primary" : "border-transparent text-secondary"
                }`
              }
            >
              {t(`team_calendar.tabs.${tab}`)}
            </NavLink>
          ))}
        </nav>
        {error && (
          <div className="flex items-center gap-2 rounded-lg border border-danger-subtle bg-danger-subtle p-3 text-13 text-danger-primary">
            <AlertTriangle className="size-4 shrink-0" /> {error}
          </div>
        )}
        <Outlet />
      </main>
    </>
  );
}

export default observer(TeamCalendarPage);
