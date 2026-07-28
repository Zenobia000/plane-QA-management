/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import { AlertTriangle } from "lucide-react";
import { NavLink, Outlet, useParams } from "react-router";
import { useTranslation } from "@plane/i18n";
import { PageHead } from "@/components/core/page-title";
import { useTesting } from "@/hooks/store/use-testing";
import type { TTestingTab } from "./helpers";
import { testingPath } from "./helpers";

const TABS: TTestingTab[] = ["overview", "cases", "runs"];

function TestingPage() {
  const { t } = useTranslation();
  const { workspaceSlug, projectId } = useParams();
  const { error, fetchLibrary } = useTesting();

  useEffect(() => {
    if (workspaceSlug && projectId) void fetchLibrary(workspaceSlug, projectId);
  }, [fetchLibrary, projectId, workspaceSlug]);

  if (!workspaceSlug || !projectId) return null;

  return (
    <>
      <PageHead title={t("testing.title")} />
      <main className="mx-auto flex h-full w-full max-w-6xl flex-col gap-5 p-6">
        <nav className="flex gap-1 border-b border-subtle" aria-label="Testing sections">
          {TABS.map((tab) => (
            <NavLink
              key={tab}
              to={testingPath({ workspaceSlug, projectId, tab })}
              className={({ isActive }) =>
                `border-b-2 px-3 py-2 text-13 font-medium ${
                  isActive ? "border-accent-strong text-primary" : "border-transparent text-secondary"
                }`
              }
            >
              {t(`testing.tabs.${tab}`)}
            </NavLink>
          ))}
        </nav>
        {error && (
          <div className="flex items-center gap-2 rounded-lg border border-danger-subtle bg-danger-subtle p-3 text-13 text-danger-primary">
            <AlertTriangle className="size-4 shrink-0" /> {error}
          </div>
        )}
        <Outlet />
      </main>
    </>
  );
}

export default observer(TestingPage);
