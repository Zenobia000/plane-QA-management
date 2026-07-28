import { describe, expect, it, vi } from "vitest";
import type { TestingService } from "@plane/services";
import type { TReleaseEvidence, TTestCase, TTestFolder, TTestResult, TTestRun } from "@plane/types";
import { TestingStore } from "./testing.store";

const capability = {
  enabled: true,
  stage: "test",
  capabilities: { test_cases: true, test_runs: true, reports: true, automation_ingestion: true },
};
const overview = {
  library: { total: 0, requirement_linked: 0, linked_percent: 0 },
  requirements: { total: 0, covered: 0, uncovered: 0, coverage_percent: 0 },
  runs: { total: 0, active: 0 },
  latest_run: null,
  open_defects: 0,
  release_evidence: [],
  release_gate: { ready: false, blockers: [] },
  scorecards: [],
};

const serviceMock = () =>
  ({
    getCapabilities: vi.fn().mockResolvedValue(capability),
    getOverview: vi.fn().mockResolvedValue(overview),
    getRequirementCoverage: vi.fn().mockResolvedValue({ total: 0, covered: 0, uncovered: 0, work_items: [] }),
    getTestCases: vi.fn().mockResolvedValue([]),
    getFolders: vi.fn().mockResolvedValue([]),
    getTestRuns: vi.fn().mockResolvedValue([]),
    createTestCase: vi.fn(),
    archiveTestCase: vi.fn(),
    uploadTestCaseAttachment: vi.fn(),
    deleteTestCaseAttachment: vi.fn(),
    recordResult: vi.fn(),
    updateFolder: vi.fn(),
    deleteFolder: vi.fn(),
    upsertReleaseEvidence: vi.fn(),
    deleteReleaseEvidence: vi.fn(),
  }) as unknown as TestingService;

const folder = {
  id: "folder",
  name: "Checkout",
  parent_id: null,
  sort_order: 0,
  created_at: "2026-07-14T00:00:00Z",
  updated_at: "2026-07-14T00:00:00Z",
} satisfies TTestFolder;

describe("TestingStore", () => {
  it("deduplicates concurrent project loads", async () => {
    const service = serviceMock();
    const store = new TestingStore(service);
    await Promise.all([store.fetchLibrary("workspace", "project"), store.fetchLibrary("workspace", "project")]);
    expect(service.getTestCases).toHaveBeenCalledTimes(1);
    expect(service.getTestRuns).toHaveBeenCalledTimes(1);
  });

  it("does not mutate normalized state when create fails", async () => {
    const service = serviceMock();
    vi.mocked(service.createTestCase).mockRejectedValue(new Error("network"));
    const store = new TestingStore(service);
    await expect(store.createCase("workspace", "project", { title: "Failed create" })).rejects.toThrow("network");
    expect(store.cases).toEqual({});
  });

  it("replaces the folder in normalized state after a rename", async () => {
    const service = serviceMock();
    vi.mocked(service.updateFolder).mockResolvedValue({ ...folder, name: "Checkout v2" });
    const store = new TestingStore(service);
    store.folders[folder.id] = folder;

    await store.renameFolder("workspace", "project", folder.id, "Checkout v2");

    expect(service.updateFolder).toHaveBeenCalledWith("workspace", "project", folder.id, { name: "Checkout v2" });
    expect(store.folders[folder.id].name).toBe("Checkout v2");
  });

  it("drops the folder from normalized state after a delete", async () => {
    const service = serviceMock();
    vi.mocked(service.deleteFolder).mockResolvedValue(undefined);
    const store = new TestingStore(service);
    store.folders[folder.id] = folder;

    await store.deleteFolder("workspace", "project", folder.id);

    expect(store.folders).toEqual({});
  });

  it("keeps a non-empty folder when the server rejects the delete", async () => {
    const service = serviceMock();
    const conflict = { error: "Only an empty test folder can be deleted." };
    vi.mocked(service.deleteFolder).mockRejectedValue(conflict);
    const store = new TestingStore(service);
    store.folders[folder.id] = folder;

    await expect(store.deleteFolder("workspace", "project", folder.id)).rejects.toEqual(conflict);
    expect(store.folders[folder.id]).toEqual(folder);
  });

  it("keeps a test case when archiving fails", async () => {
    const service = serviceMock();
    vi.mocked(service.archiveTestCase).mockRejectedValue(new Error("network"));
    const store = new TestingStore(service);
    store.cases.case = { id: "case" } as TTestCase;

    await expect(store.archiveCase("workspace", "project", "case")).rejects.toThrow("network");

    expect(store.cases.case).toBeDefined();
  });

  it("adds and removes test-case attachments after successful service writes", async () => {
    const service = serviceMock();
    const attachment = {
      id: "asset",
      attributes: { name: "evidence.png", type: "image/png", size: 3 },
      size: 3,
      created_at: "",
      created_by_id: null,
      download_url: "/download",
      preview_url: "/preview",
    };
    vi.mocked(service.uploadTestCaseAttachment).mockResolvedValue(attachment);
    vi.mocked(service.deleteTestCaseAttachment).mockResolvedValue(undefined);
    const store = new TestingStore(service);

    await store.uploadAttachment("workspace", "project", "case", new File(["png"], "evidence.png"));
    expect(store.attachments.case).toEqual([attachment]);

    await store.deleteAttachment("workspace", "project", "case", attachment.id);
    expect(store.attachments.case).toEqual([]);
  });

  it("refreshes the release gate after evidence is upserted or deleted", async () => {
    const service = serviceMock();
    const evidence = {
      id: "evidence",
      kind: "slo",
      key: "checkout-latency",
      name: "Checkout latency",
      status: "passing",
      detail: "p95 under 250ms",
      source_url: "https://example.com/report",
      recorded_at: "2026-07-28T00:00:00Z",
    } satisfies TReleaseEvidence;
    vi.mocked(service.upsertReleaseEvidence).mockResolvedValue(evidence);
    vi.mocked(service.deleteReleaseEvidence).mockResolvedValue(undefined);
    const store = new TestingStore(service);

    await expect(store.upsertReleaseEvidence("workspace", "project", evidence)).resolves.toEqual(evidence);
    expect(service.getOverview).toHaveBeenCalledTimes(1);

    await store.deleteReleaseEvidence("workspace", "project", evidence.key);
    expect(service.deleteReleaseEvidence).toHaveBeenCalledWith("workspace", "project", evidence.key);
    expect(service.getOverview).toHaveBeenCalledTimes(2);
  });

  it("appends a retest and recomputes progress from latest statuses", async () => {
    const service = serviceMock();
    const result = {
      id: "result-2",
      sequence: 2,
      status: "passed",
      actual_result: {},
      duration_ms: null,
      executed_by_id: null,
      created_at: "2026-07-14T00:00:00Z",
      defects: [],
    } satisfies TTestResult;
    vi.mocked(service.recordResult).mockResolvedValue(result);
    const store = new TestingStore(service);
    store.runs.run = {
      id: "run",
      status: "active",
      run_type: "fixed",
      name: "Run",
      description: {},
      build: "",
      configuration: {},
      cycle_id: null,
      module_id: null,
      closed_at: null,
      created_at: "",
      updated_at: "",
      progress: { total: 1, open: 0, passed: 0, failed: 1, blocked: 0, skipped: 0 },
      run_cases: [
        {
          id: "case",
          test_case_id: "test-case",
          position: 1,
          latest_status: "failed",
          results: [{ ...result, id: "result-1", sequence: 1, status: "failed" }],
          test_case_version: {} as TTestCase["current"],
        },
      ],
    } satisfies TTestRun;

    await expect(store.recordResult("workspace", "project", "run", "case", { status: "passed" })).resolves.toEqual(
      result
    );

    expect(store.runs.run.run_cases[0].results).toHaveLength(2);
    expect(store.runs.run.progress).toEqual({
      total: 1,
      open: 0,
      passed: 1,
      failed: 0,
      blocked: 0,
      skipped: 0,
    });
  });
});
