/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Navigate } from "react-router";

/**
 * `/testing` has no view of its own -- redirecting keeps one canonical URL per
 * view instead of letting the overview answer to two addresses.
 */
export default function TestingIndexRoute() {
  return <Navigate to="overview" replace />;
}
