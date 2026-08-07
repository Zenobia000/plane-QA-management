/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { SettingsView } from "../components/settings-view";

/**
 * Not wrapped in `AvailabilitySurface`.
 *
 * The other tabs gate on a capability flag because they render data the slice may not have
 * built yet. Settings is where the data gets created in the first place — gating it would
 * mean a workspace with nothing configured could never configure anything.
 */
export default function TeamCalendarSettingsRoute() {
  return <SettingsView />;
}
