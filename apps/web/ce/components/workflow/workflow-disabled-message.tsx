/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { cn } from "@plane/utils";

type Props = {
  parentStateId: string;
  className?: string;
};

/**
 * Why a state is not offered.
 *
 * Named rather than silent: a state that vanishes from a dropdown with no explanation reads
 * as a bug, and the person who hits it has no way to find out it was a rule.
 */
export function WorkFlowDisabledMessage({ className }: Props) {
  return (
    <p className={cn("px-2 py-1.5 text-11 text-tertiary", className)}>
      The project&apos;s workflow does not allow moving to this state from here.
    </p>
  );
}
