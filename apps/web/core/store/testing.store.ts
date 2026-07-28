/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { action, makeObservable, observable, runInAction } from "mobx";
import { TestingService } from "@plane/services";
import type {
  TTestCase,
  TTestCaseInput,
  TTestDefect,
  TTestDefectInput,
  TTestFolder,
  TTestResultAttachment,
  TTestResultInput,
  TTestingCapabilities,
  TTestingOverview,
  TTestingRequirementCoverage,
  TTestRun,
  TTestRunInput,
} from "@plane/types";

export interface ITestingStore {
  capability: TTestingCapabilities | null;
  overview: TTestingOverview | null;
  requirementCoverage: TTestingRequirementCoverage | null;
  cases: Record<string, TTestCase>;
  folders: Record<string, TTestFolder>;
  runs: Record<string, TTestRun>;
  loading: boolean;
  error: string | null;
  fetchLibrary: (workspaceSlug: string, projectId: string) => Promise<void>;
  createCase: (workspaceSlug: string, projectId: string, input: TTestCaseInput) => Promise<TTestCase>;
  updateCase: (
    workspaceSlug: string,
    projectId: string,
    caseId: string,
    input: Partial<TTestCaseInput>
  ) => Promise<TTestCase>;
  createFolder: (
    workspaceSlug: string,
    projectId: string,
    name: string,
    parentId?: string | null
  ) => Promise<TTestFolder>;
  renameFolder: (workspaceSlug: string, projectId: string, folderId: string, name: string) => Promise<TTestFolder>;
  deleteFolder: (workspaceSlug: string, projectId: string, folderId: string) => Promise<void>;
  linkWorkItem: (workspaceSlug: string, projectId: string, caseId: string, issueId: string) => Promise<void>;
  unlinkWorkItem: (workspaceSlug: string, projectId: string, caseId: string, issueId: string) => Promise<void>;
  exportLibraryCSV: (workspaceSlug: string, projectId: string) => Promise<string>;
  importLibraryCSV: (workspaceSlug: string, projectId: string, csvText: string) => Promise<number>;
  createRun: (workspaceSlug: string, projectId: string, input: TTestRunInput) => Promise<TTestRun>;
  recordResult: (
    workspaceSlug: string,
    projectId: string,
    runId: string,
    runCaseId: string,
    input: TTestResultInput
  ) => Promise<void>;
  closeRun: (workspaceSlug: string, projectId: string, runId: string) => Promise<void>;
  listResultAttachments: (
    workspaceSlug: string,
    projectId: string,
    runId: string,
    runCaseId: string,
    resultId: string
  ) => Promise<TTestResultAttachment[]>;
  attachResultFile: (
    workspaceSlug: string,
    projectId: string,
    runId: string,
    runCaseId: string,
    resultId: string,
    file: File
  ) => Promise<TTestResultAttachment>;
  detachResultFile: (
    workspaceSlug: string,
    projectId: string,
    runId: string,
    runCaseId: string,
    resultId: string,
    assetId: string
  ) => Promise<void>;
  createDefect: (
    workspaceSlug: string,
    projectId: string,
    runId: string,
    runCaseId: string,
    resultId: string,
    input?: TTestDefectInput
  ) => Promise<TTestDefect>;
}

export class TestingStore implements ITestingStore {
  capability: TTestingCapabilities | null = null;
  overview: TTestingOverview | null = null;
  requirementCoverage: TTestingRequirementCoverage | null = null;
  cases: Record<string, TTestCase> = {};
  folders: Record<string, TTestFolder> = {};
  runs: Record<string, TTestRun> = {};
  loading = false;
  error: string | null = null;
  private inflightFetches = new Map<string, Promise<void>>();

  constructor(private service: TestingService = new TestingService()) {
    makeObservable(this, {
      capability: observable.ref,
      overview: observable.ref,
      requirementCoverage: observable.ref,
      cases: observable,
      folders: observable,
      runs: observable,
      loading: observable,
      error: observable,
      fetchLibrary: action,
      createCase: action,
      updateCase: action,
      createFolder: action,
      renameFolder: action,
      deleteFolder: action,
      linkWorkItem: action,
      unlinkWorkItem: action,
      importLibraryCSV: action,
      createRun: action,
      recordResult: action,
      closeRun: action,
      createDefect: action,
    });
  }

  fetchLibrary = (workspaceSlug: string, projectId: string) => {
    const key = `${workspaceSlug}:${projectId}`;
    const existing = this.inflightFetches.get(key);
    if (existing) return existing;
    const request = this.fetchLibraryData(workspaceSlug, projectId).finally(() => this.inflightFetches.delete(key));
    this.inflightFetches.set(key, request);
    return request;
  };

  private fetchLibraryData = async (workspaceSlug: string, projectId: string) => {
    this.loading = true;
    this.error = null;
    try {
      const [capability, overview, requirementCoverage, cases, folders, runs] = await Promise.all([
        this.service.getCapabilities(workspaceSlug, projectId),
        this.service.getOverview(workspaceSlug, projectId),
        this.service.getRequirementCoverage(workspaceSlug, projectId),
        this.service.getTestCases(workspaceSlug, projectId),
        this.service.getFolders(workspaceSlug, projectId),
        this.service.getTestRuns(workspaceSlug, projectId),
      ]);
      runInAction(() => {
        this.capability = capability;
        this.overview = overview;
        this.requirementCoverage = requirementCoverage;
        this.cases = Object.fromEntries(cases.map((testCase) => [testCase.id, testCase]));
        this.folders = Object.fromEntries(folders.map((folder) => [folder.id, folder]));
        this.runs = Object.fromEntries(runs.map((testRun) => [testRun.id, testRun]));
      });
    } catch (error) {
      runInAction(() => {
        this.error = error instanceof Error ? error.message : "Unable to load the test library.";
      });
    } finally {
      runInAction(() => {
        this.loading = false;
      });
    }
  };

  updateCase = async (workspaceSlug: string, projectId: string, caseId: string, input: Partial<TTestCaseInput>) => {
    const updated = await this.service.updateTestCase(workspaceSlug, projectId, caseId, input);
    runInAction(() => {
      this.cases[caseId] = updated;
    });
    return updated;
  };

  createFolder = async (workspaceSlug: string, projectId: string, name: string, parentId?: string | null) => {
    const folder = await this.service.createFolder(workspaceSlug, projectId, {
      name,
      parent_id: parentId ?? null,
    });
    runInAction(() => {
      this.folders[folder.id] = folder;
    });
    return folder;
  };

  renameFolder = async (workspaceSlug: string, projectId: string, folderId: string, name: string) => {
    const updated = await this.service.updateFolder(workspaceSlug, projectId, folderId, { name });
    runInAction(() => {
      this.folders[folderId] = updated;
    });
    return updated;
  };

  deleteFolder = async (workspaceSlug: string, projectId: string, folderId: string) => {
    await this.service.deleteFolder(workspaceSlug, projectId, folderId);
    runInAction(() => {
      delete this.folders[folderId];
    });
  };

  linkWorkItem = async (workspaceSlug: string, projectId: string, caseId: string, issueId: string) => {
    await this.service.linkWorkItem(workspaceSlug, projectId, caseId, issueId);
    runInAction(() => {
      const testCase = this.cases[caseId];
      if (testCase && !testCase.work_item_ids.includes(issueId)) testCase.work_item_ids.push(issueId);
    });
  };

  unlinkWorkItem = async (workspaceSlug: string, projectId: string, caseId: string, issueId: string) => {
    await this.service.unlinkWorkItem(workspaceSlug, projectId, caseId, issueId);
    runInAction(() => {
      const testCase = this.cases[caseId];
      if (!testCase) return;
      testCase.work_item_ids = testCase.work_item_ids.filter((id) => id !== issueId);
      testCase.work_items = testCase.work_items.filter((item) => item.id !== issueId);
    });
  };

  exportLibraryCSV = (workspaceSlug: string, projectId: string) =>
    this.service.exportLibraryCSV(workspaceSlug, projectId);

  importLibraryCSV = async (workspaceSlug: string, projectId: string, csvText: string) => {
    const result = await this.service.importLibraryCSV(workspaceSlug, projectId, csvText);
    const [cases, folders] = await Promise.all([
      this.service.getTestCases(workspaceSlug, projectId),
      this.service.getFolders(workspaceSlug, projectId),
    ]);
    runInAction(() => {
      this.cases = Object.fromEntries(cases.map((item) => [item.id, item]));
      this.folders = Object.fromEntries(folders.map((item) => [item.id, item]));
    });
    return result.created;
  };

  createCase = async (workspaceSlug: string, projectId: string, input: TTestCaseInput) => {
    const created = await this.service.createTestCase(workspaceSlug, projectId, input);
    runInAction(() => {
      this.cases[created.id] = created;
    });
    return created;
  };

  createRun = async (workspaceSlug: string, projectId: string, input: TTestRunInput) => {
    const created = await this.service.createTestRun(workspaceSlug, projectId, input);
    runInAction(() => {
      this.runs[created.id] = created;
    });
    return created;
  };

  recordResult = async (
    workspaceSlug: string,
    projectId: string,
    runId: string,
    runCaseId: string,
    input: TTestResultInput
  ) => {
    const result = await this.service.recordResult(workspaceSlug, projectId, runId, runCaseId, input);
    runInAction(() => {
      const run = this.runs[runId];
      const runCase = run?.run_cases.find((item) => item.id === runCaseId);
      if (!run || !runCase) return;
      runCase.results.push(result);
      runCase.latest_status = result.status;
      const statuses = ["open", "passed", "failed", "blocked", "skipped"] as const;
      run.progress = {
        total: run.run_cases.length,
        ...Object.fromEntries(
          statuses.map((status) => [status, run.run_cases.filter((item) => item.latest_status === status).length])
        ),
      } as TTestRun["progress"];
    });
  };

  listResultAttachments = (
    workspaceSlug: string,
    projectId: string,
    runId: string,
    runCaseId: string,
    resultId: string
  ) => this.service.getResultAttachments(workspaceSlug, projectId, runId, runCaseId, resultId);

  attachResultFile = (
    workspaceSlug: string,
    projectId: string,
    runId: string,
    runCaseId: string,
    resultId: string,
    file: File
  ) => this.service.uploadResultAttachment(workspaceSlug, projectId, runId, runCaseId, resultId, file);

  detachResultFile = (
    workspaceSlug: string,
    projectId: string,
    runId: string,
    runCaseId: string,
    resultId: string,
    assetId: string
  ) => this.service.deleteResultAttachment(workspaceSlug, projectId, runId, runCaseId, resultId, assetId);

  closeRun = async (workspaceSlug: string, projectId: string, runId: string) => {
    const updated = await this.service.closeTestRun(workspaceSlug, projectId, runId);
    runInAction(() => {
      this.runs[runId] = updated;
    });
  };

  createDefect = async (
    workspaceSlug: string,
    projectId: string,
    runId: string,
    runCaseId: string,
    resultId: string,
    input: TTestDefectInput = {}
  ) => {
    const defect = await this.service.createDefect(workspaceSlug, projectId, runId, runCaseId, resultId, input);
    runInAction(() => {
      const result = this.runs[runId]?.run_cases
        .find((item) => item.id === runCaseId)
        ?.results.find((item) => item.id === resultId);
      result?.defects.push(defect);
    });
    return defect;
  };
}
