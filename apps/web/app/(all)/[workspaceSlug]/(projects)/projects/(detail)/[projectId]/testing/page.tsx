/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { AlertTriangle } from "lucide-react";
import { useParams } from "next/navigation";
import { PageHead } from "@/components/core/page-title";
import { useTesting } from "@/hooks/store/use-testing";
import { TestLibraryView } from "./components/library-view";
import { TestingOverviewView } from "./components/overview-view";
import { TestRunsView } from "./components/runs-view";

function TestingPage() {
  const { workspaceSlug, projectId } = useParams();
  const { error, fetchLibrary } = useTesting();
  const [tab, setTab] = useState<"overview" | "library" | "runs">("overview");
  const workspace = workspaceSlug?.toString();
  const project = projectId?.toString();

  useEffect(() => {
    if (workspace && project) void fetchLibrary(workspace, project);
  }, [fetchLibrary, project, workspace]);

  if (!workspace || !project) return null;

  return (
    <>
      <PageHead title="Testing" />
      <main className="mx-auto flex h-full w-full max-w-6xl flex-col gap-5 p-6">
        <nav className="flex gap-1 border-b border-subtle" aria-label="Testing sections">
          {(["overview", "library", "runs"] as const).map((item) => (
            <button
              type="button"
              key={item}
              onClick={() => setTab(item)}
              className={`border-b-2 px-3 py-2 text-13 font-medium capitalize ${
                tab === item ? "border-accent-strong text-primary" : "border-transparent text-secondary"
              }`}
            >
              {item === "library" ? "Test cases" : item === "runs" ? "Test runs" : "Overview"}
            </button>
          ))}
        </nav>
        {error && (
          <div className="flex items-center gap-2 rounded-lg border border-danger-subtle bg-danger-subtle p-3 text-13 text-danger-primary">
            <AlertTriangle className="size-4 shrink-0" /> {error}
          </div>
        )}
        {tab === "overview" ? (
          <TestingOverviewView />
        ) : tab === "library" ? (
          <TestLibraryView workspaceSlug={workspace} projectId={project} />
        ) : (
          <TestRunsView workspaceSlug={workspace} projectId={project} />
        )}
      </main>
    </>
  );
}

export default observer(TestingPage);
