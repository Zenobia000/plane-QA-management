/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { AllocationMatrix } from "../components/allocation-matrix";
import { AvailabilitySurface } from "../components/availability-surface";

export default function TeamCalendarAllocationRoute() {
  return (
    <AvailabilitySurface tab="allocation">
      <AllocationMatrix />
    </AvailabilitySurface>
  );
}
