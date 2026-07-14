/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TTestingDocument = Record<string, unknown>;

export type TTestStep = {
  id: string;
  position: number;
  action: TTestingDocument;
  expected_result: TTestingDocument;
};

export type TTestCaseVersion = {
  id: string;
  version: number;
  title: string;
  description: TTestingDocument;
  preconditions: TTestingDocument;
  priority: "urgent" | "high" | "medium" | "low" | "none";
  tags: string[];
  steps: TTestStep[];
  created_at: string;
  created_by_id: string | null;
};

export type TTestCase = {
  id: string;
  sequence: number;
  folder_id: string | null;
  current_version: number;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
  current: TTestCaseVersion;
  work_item_ids: string[];
  latest_status: TTestRunCaseStatus | null;
};

export type TTestCaseInput = {
  title: string;
  folder_id?: string | null;
  description?: TTestingDocument;
  preconditions?: TTestingDocument;
  priority?: TTestCaseVersion["priority"];
  tags?: string[];
  steps?: Array<Pick<TTestStep, "action" | "expected_result">>;
};

export type TTestFolder = {
  id: string;
  name: string;
  parent_id: string | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
};

export type TTestingCapabilities = {
  enabled: boolean;
  stage: string;
  capabilities: {
    test_cases: boolean;
    test_runs: boolean;
    reports: boolean;
    automation_ingestion: boolean;
  };
};

export type TTestingOverview = {
  library: { total: number; requirement_linked: number; coverage_percent: number };
  runs: { total: number; active: number };
  latest_run:
    | ({
        id: string;
        name: string;
        status: "draft" | "active" | "completed";
      } & Record<TTestRunCaseStatus, number>)
    | null;
  open_defects: number;
  scorecards: Array<
    {
      id: string;
      name: string;
      build: string;
      configuration: TTestingDocument;
      status: "draft" | "active" | "completed";
    } & Record<TTestRunCaseStatus, number>
  >;
  release_gate: { ready: boolean; blockers: string[] };
};

export type TTestingRequirementCoverage = {
  total: number;
  covered: number;
  uncovered: number;
  work_items: Array<{
    work_item_id: string;
    sequence_id: number;
    name: string;
    state_group: string | null;
    covered: boolean;
    test_case_ids: string[];
    latest_status: TTestRunCaseStatus | null;
  }>;
};

export type TTestResultStatus = "passed" | "failed" | "blocked" | "skipped";
export type TTestRunCaseStatus = "open" | TTestResultStatus;

export type TTestDefect = {
  id: string;
  name: string;
  sequence_id: number;
  state_group: string | null;
  created_at: string;
};

export type TTestResult = {
  id: string;
  sequence: number;
  status: TTestResultStatus;
  actual_result: TTestingDocument;
  duration_ms: number | null;
  executed_by_id: string | null;
  created_at: string;
  defects: TTestDefect[];
};

export type TTestRunCase = {
  id: string;
  test_case_id: string;
  test_case_version: TTestCaseVersion;
  position: number;
  latest_status: TTestRunCaseStatus;
  results: TTestResult[];
};

export type TTestRunProgress = Record<TTestRunCaseStatus, number> & { total: number };

export type TTestRun = {
  id: string;
  name: string;
  description: TTestingDocument;
  status: "draft" | "active" | "completed";
  run_type: "fixed" | "live";
  build: string;
  configuration: TTestingDocument;
  cycle_id: string | null;
  module_id: string | null;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
  progress: TTestRunProgress;
  run_cases: TTestRunCase[];
};

export type TTestRunInput = {
  name: string;
  description?: TTestingDocument;
  build?: string;
  configuration?: TTestingDocument;
  cycle_id?: string | null;
  module_id?: string | null;
  test_case_ids: string[];
};

export type TTestResultInput = {
  status: TTestResultStatus;
  actual_result?: TTestingDocument;
  duration_ms?: number | null;
};

export type TTestDefectInput = {
  name?: string;
  priority?: "urgent" | "high" | "medium" | "low" | "none";
};
