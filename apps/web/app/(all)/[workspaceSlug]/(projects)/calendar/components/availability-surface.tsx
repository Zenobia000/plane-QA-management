/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ReactNode } from "react";
import { observer } from "mobx-react";
import { CalendarClock, CalendarOff, PieChart } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import type { TAvailabilityTab } from "@plane/types";
import { useAvailability } from "@/hooks/store/use-availability";
import { isTabReady } from "../helpers";

const ICONS: Record<TAvailabilityTab, typeof CalendarClock> = {
  schedule: CalendarClock,
  leave: CalendarOff,
  allocation: PieChart,
};

type Props = {
  tab: TAvailabilityTab;
  children?: ReactNode;
};

/**
 * Loading, not-yet-built, or the real thing.
 *
 * Which of the three is decided by the capability payload rather than by what happens to
 * be imported, so a tab whose slice has not landed says so instead of rendering controls
 * that do nothing. `testing-platform-workflow.md` §12 asks for exactly this: the route,
 * the navigation and the states ship first and get exercised, then the feature fills in.
 */
export const AvailabilitySurface = observer(function AvailabilitySurface({ tab, children }: Props) {
  const { t } = useTranslation();
  const { capability, loading } = useAvailability();
  const Icon = ICONS[tab];

  if (loading && !capability) {
    return (
      <div className="flex flex-col gap-3" aria-busy="true">
        <div className="h-8 w-48 animate-pulse rounded bg-surface-2" />
        <div className="h-32 w-full animate-pulse rounded bg-surface-2" />
      </div>
    );
  }

  if (!isTabReady(capability, tab)) {
    return (
      <section className="flex flex-1 flex-col items-center justify-center gap-3 py-16 text-center">
        <Icon className="size-8 text-tertiary" aria-hidden />
        <h2 className="text-15 font-medium text-primary">{t(`team_calendar.empty.${tab}.title`)}</h2>
        <p className="max-w-md text-13 text-secondary">{t(`team_calendar.empty.${tab}.description`)}</p>
      </section>
    );
  }

  return <>{children}</>;
});
