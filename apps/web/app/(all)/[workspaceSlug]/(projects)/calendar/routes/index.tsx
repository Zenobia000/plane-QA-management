/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Navigate } from "react-router";

/**
 * `/calendar` has no view of its own. Schedule is the default because "when can we talk"
 * is the question this page gets opened for daily; leave and allocation are asked monthly
 * and quarterly. See `docs/planning/team-calendar.md`.
 */
export default function TeamCalendarIndexRoute() {
  return <Navigate to="schedule" replace />;
}
