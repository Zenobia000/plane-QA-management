/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TAvailabilityCapabilities, TAvailabilityTab } from "@plane/types";

export const AVAILABILITY_TABS: TAvailabilityTab[] = ["schedule", "leave", "allocation"];

type TAvailabilityPath = {
  workspaceSlug: string;
  tab?: TAvailabilityTab;
};

export const availabilityPath = ({ workspaceSlug, tab }: TAvailabilityPath) =>
  tab ? `/${workspaceSlug}/calendar/${tab}` : `/${workspaceSlug}/calendar`;

/**
 * Which capability flag decides whether a tab has anything to render.
 *
 * The schedule tab needs `schedule`; the common-slot finder inside it is gated separately
 * by `overlap` so the week view can ship before the finder does.
 */
const TAB_CAPABILITY: Record<TAvailabilityTab, keyof TAvailabilityCapabilities["capabilities"]> = {
  schedule: "schedule",
  leave: "leave",
  allocation: "allocation",
};

export const isTabReady = (capability: TAvailabilityCapabilities | null, tab: TAvailabilityTab): boolean =>
  Boolean(capability?.enabled && capability.capabilities[TAB_CAPABILITY[tab]]);
