/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useParams } from "react-router";
import { TestRunsView } from "../components/runs-view";

/** Serves `/testing/runs`, `/testing/runs/:runId`, and `.../:runCaseId`. */
export default function TestingRunsRoute() {
  const { workspaceSlug, projectId } = useParams();
  if (!workspaceSlug || !projectId) return null;
  return <TestRunsView workspaceSlug={workspaceSlug} projectId={projectId} />;
}
