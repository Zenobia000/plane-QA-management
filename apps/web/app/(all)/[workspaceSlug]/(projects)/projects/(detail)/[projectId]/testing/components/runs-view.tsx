/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { orderBy } from "lodash-es";
import { Play, Plus } from "lucide-react";
import { observer } from "mobx-react";
import { useNavigate, useParams } from "react-router";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import type { TTestResultInput, TTestRunInput } from "@plane/types";
import { useTesting } from "@/hooks/store/use-testing";
import { testingPath } from "../helpers";
import { ExecutionWorkspace } from "./execution-workspace";
import { TestRunBuilder } from "./run-builder";

type Props = { workspaceSlug: string; projectId: string };

export const TestRunsView = observer(function TestRunsView({ workspaceSlug, projectId }: Props) {
  const { t } = useTranslation();
  const { cases, runs, createRun, recordResult, closeRun, createDefect } = useTesting();
  const { runId, runCaseId } = useParams();
  const navigate = useNavigate();
  const [building, setBuilding] = useState(false);
  const selectedRun = runId ? runs[runId] : undefined;
  const testCases = orderBy(Object.values(cases), ["sequence"], ["asc"]);
  const testRuns = orderBy(Object.values(runs), ["created_at"], ["desc"]);

  const goToRun = (id: string, options?: { replace?: boolean }) =>
    navigate(testingPath({ workspaceSlug, projectId, tab: "runs", runId: id }), options);

  if (runId && !selectedRun) {
    return (
      <section className="flex flex-1 flex-col items-center justify-center gap-3 rounded-lg border border-subtle bg-surface-1 p-8">
        <p className="text-13 text-secondary">{t("testing.runs.not_found")}</p>
        <Button variant="secondary" onClick={() => navigate(testingPath({ workspaceSlug, projectId, tab: "runs" }))}>
          {t("testing.runs.back_to_runs")}
        </Button>
      </section>
    );
  }

  if (selectedRun) {
    return (
      <ExecutionWorkspace
        run={selectedRun}
        selectedRunCaseId={runCaseId}
        onSelectRunCase={(id, options) =>
          navigate(
            testingPath({ workspaceSlug, projectId, tab: "runs", runId: selectedRun.id, runCaseId: id }),
            options
          )
        }
        onBack={() => navigate(testingPath({ workspaceSlug, projectId, tab: "runs" }))}
        onResult={(id: string, input: TTestResultInput) =>
          recordResult(workspaceSlug, projectId, selectedRun.id, id, input)
        }
        onClose={() => closeRun(workspaceSlug, projectId, selectedRun.id)}
        onCreateDefect={(id, resultId) => createDefect(workspaceSlug, projectId, selectedRun.id, id, resultId)}
      />
    );
  }

  if (building) {
    return (
      <TestRunBuilder
        testCases={testCases}
        onCancel={() => setBuilding(false)}
        onCreate={async (input: TTestRunInput) => {
          const created = await createRun(workspaceSlug, projectId, input);
          setBuilding(false);
          goToRun(created.id);
        }}
      />
    );
  }

  return (
    <>
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-20 font-semibold text-primary">{t("testing.runs.heading")}</h1>
          <p className="mt-1 text-13 text-secondary">{t("testing.runs.subheading")}</p>
        </div>
        <Button variant="primary" size="lg" onClick={() => setBuilding(true)} disabled={!testCases.length}>
          <Plus className="size-4" /> {t("testing.runs.create")}
        </Button>
      </div>
      <section className="overflow-hidden rounded-lg border border-subtle bg-surface-1">
        {testRuns.map((run) => (
          <button
            type="button"
            key={run.id}
            onClick={() => goToRun(run.id)}
            className="grid w-full grid-cols-[1fr_8rem_8rem_3rem] items-center gap-4 border-b border-subtle px-4 py-3 text-left last:border-b-0 hover:bg-surface-2"
          >
            <span>
              <span className="block text-13 font-medium text-primary">{run.name}</span>
              <span className="text-11 text-tertiary">{run.build || t("testing.runs.no_build")}</span>
            </span>
            <span className="text-12 text-secondary capitalize">{run.status}</span>
            <span className="text-12 text-secondary">
              {run.progress.total - run.progress.open}/{run.progress.total}
            </span>
            <Play className="size-4 text-tertiary" />
          </button>
        ))}
        {!testRuns.length && <p className="p-8 text-center text-13 text-secondary">{t("testing.runs.empty")}</p>}
      </section>
    </>
  );
});
