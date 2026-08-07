/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TUpdateStatus } from "@plane/types";

/**
 * How a health verdict is named and coloured.
 *
 * Kept out of `status-pill.tsx` so that file exports a component and nothing else: Fast
 * Refresh can only preserve component state in modules whose exports are all components.
 */

/** Translation keys rather than English, so the verdict reads in the reader's language. */
export const UPDATE_STATUS_KEYS: Record<TUpdateStatus, string> = {
  on_track: "project_overview.updates.status.on_track",
  at_risk: "project_overview.updates.status.at_risk",
  off_track: "project_overview.updates.status.off_track",
};

export const STATUS_CLASSES: Record<TUpdateStatus, string> = {
  on_track: "bg-success-subtle text-success-primary",
  at_risk: "bg-warning-subtle text-warning-primary",
  off_track: "bg-danger-subtle text-danger-primary",
};
