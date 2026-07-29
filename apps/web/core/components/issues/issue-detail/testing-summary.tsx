/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { useEffect, useState } from "react";
import { FlaskConical } from "lucide-react";
import { Link } from "react-router";
import { useTranslation } from "@plane/i18n";
import { TestingService } from "@plane/services";
import type { TTestCase, TTestRunCaseStatus } from "@plane/types";

const testingService = new TestingService();

type Props = { workspaceSlug: string; projectId: string; issueId: string };

const statusStyle: Record<string, string> = {
  passed: "bg-success-subtle text-success-primary",
  failed: "bg-danger-subtle text-danger-primary",
  blocked: "bg-warning-subtle text-warning-primary",
  skipped: "bg-layer-2 text-tertiary",
  open: "bg-layer-2 text-secondary",
};

const sourceOf = (testCase: TTestCase) => (testCase.current.tags.includes("automated") ? "automated" : "manual");

/**
 * A delivery decision starts here rather than in the Testing tab, so the panel
 * has to answer "is this verified" on its own and then get out of the way -- every
 * row links through to the contract it names.
 */
export function TestingWorkItemSummaryContent({
  workspaceSlug,
  projectId,
  cases,
}: Omit<Props, "issueId"> & { cases: TTestCase[] }) {
  const { t } = useTranslation();
  const testingPath = `/${workspaceSlug}/projects/${projectId}/testing`;

  if (!cases.length)
    return (
      <section className="overflow-hidden rounded-lg border border-subtle bg-surface-1" aria-label="Testing coverage">
        <div className="flex items-center justify-between border-b border-subtle px-4 py-3">
          <div className="flex items-center gap-2">
            <FlaskConical className="size-4 text-accent-primary" />
            <h3 className="text-13 font-semibold text-primary">{t("testing.work_item.heading")}</h3>
          </div>
        </div>
        <div className="px-4 py-4">
          {/* Not an empty list -- a requirement with no contract is a Definition-of-Ready
              signal, and it now blocks the release gate, so say so and offer the way out. */}
          <p className="text-12 text-secondary">{t("testing.work_item.empty")}</p>
          <Link to={`${testingPath}/cases`} className="mt-2 inline-block text-12 font-medium text-accent-primary">
            {t("testing.work_item.create_contract")}
          </Link>
        </div>
      </section>
    );

  const counts = cases.reduce<Record<string, number>>((totals, testCase) => {
    const key = testCase.latest_status ?? "open";
    totals[key] = (totals[key] ?? 0) + 1;
    return totals;
  }, {});

  return (
    <section className="overflow-hidden rounded-lg border border-subtle bg-surface-1" aria-label="Testing coverage">
      <div className="flex items-center justify-between border-b border-subtle px-4 py-3">
        <div className="flex items-center gap-2">
          <FlaskConical className="size-4 text-accent-primary" />
          <h3 className="text-13 font-semibold text-primary">{t("testing.work_item.heading")}</h3>
        </div>
        <Link to={testingPath} className="text-11 font-medium text-accent-primary hover:underline">
          {t("testing.work_item.open_testing")}
        </Link>
      </div>
      {/* Conclusion before detail: this line is all a delivery decision usually needs. */}
      <p className="border-b border-subtle px-4 py-2 text-12 text-secondary">
        {t("testing.work_item.summary", {
          total: cases.length,
          failed: (counts.failed ?? 0) + (counts.blocked ?? 0),
          unexecuted: counts.open ?? 0,
          passed: counts.passed ?? 0,
        })}
      </p>
      {cases.map((testCase) => (
        <Link
          key={testCase.id}
          to={`${testingPath}/cases/${testCase.sequence}`}
          className="grid grid-cols-[5rem_1fr_5rem_5rem] items-center gap-3 border-b border-subtle px-4 py-3 text-12 last:border-0 hover:bg-surface-2"
        >
          <span className="font-medium text-secondary">TC-{testCase.sequence}</span>
          <span className="truncate text-primary">{testCase.current.title}</span>
          <span className="text-11 text-tertiary">{t(`testing.cases.source.${sourceOf(testCase)}`)}</span>
          <span
            className={`justify-self-start rounded px-1.5 py-0.5 text-10 font-medium capitalize ${
              statusStyle[testCase.latest_status ?? "open"]
            }`}
          >
            {testCase.latest_status
              ? t(`testing.status.${testCase.latest_status as TTestRunCaseStatus}`)
              : t("testing.status.not_run")}
          </span>
        </Link>
      ))}
    </section>
  );
}

export function TestingWorkItemSummary({ workspaceSlug, projectId, issueId }: Props) {
  const [cases, setCases] = useState<TTestCase[]>();
  useEffect(() => {
    let active = true;
    void testingService
      .getWorkItemTestCases(workspaceSlug, projectId, issueId)
      .then((items) => active && setCases(items))
      .catch(() => active && setCases([]));
    return () => {
      active = false;
    };
  }, [issueId, projectId, workspaceSlug]);

  if (!cases) return null;
  return <TestingWorkItemSummaryContent workspaceSlug={workspaceSlug} projectId={projectId} cases={cases} />;
}
