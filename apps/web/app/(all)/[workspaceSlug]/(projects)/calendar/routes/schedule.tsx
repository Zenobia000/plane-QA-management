/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { AvailabilitySurface } from "../components/availability-surface";
import { WeekView } from "../components/week-view";

export default function TeamCalendarScheduleRoute() {
  return (
    <AvailabilitySurface tab="schedule">
      <WeekView />
    </AvailabilitySurface>
  );
}
