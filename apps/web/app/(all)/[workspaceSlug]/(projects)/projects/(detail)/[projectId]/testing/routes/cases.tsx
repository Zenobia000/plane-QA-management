/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useParams } from "react-router";
import { TestLibraryView } from "../components/library-view";

/** Serves both `/testing/cases` and `/testing/cases/:sequence`. */
export default function TestingCasesRoute() {
  const { workspaceSlug, projectId } = useParams();
  if (!workspaceSlug || !projectId) return null;
  return <TestLibraryView workspaceSlug={workspaceSlug} projectId={projectId} />;
}
