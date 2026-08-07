/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useTranslation } from "@plane/i18n";
import type { TUpdateStatus } from "@plane/types";

/**
 * The health verdict on a post, and the colours that carry it.
 *
 * Its own module because three places need it -- the post itself, the composer's status
 * picker, and the heading of a board grouped by status -- and the last of those lives in
 * `board-controls.tsx`, which `panel.tsx` imports. Leaving the pill in the panel would put
 * a cycle between those two files.
 */

/** Translation keys rather than English, so the pill reads in the reader's language. */
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

export function UpdateStatusPill({ status }: { status: TUpdateStatus }) {
  const { t } = useTranslation();
  return (
    <span className={`rounded px-1.5 py-0.5 text-10 font-medium ${STATUS_CLASSES[status]}`}>
      {t(UPDATE_STATUS_KEYS[status])}
    </span>
  );
}
