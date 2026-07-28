import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { TTestCase, TTestFolder, TTestRun } from "@plane/types";
import { ExecutionWorkspace } from "./execution-workspace";
import { FolderTree } from "./folder-tree";
import { TestRunBuilder } from "./run-builder";

const version = {
  id: "version",
  version: 1,
  title: "Checkout succeeds",
  description: {},
  preconditions: { text: "A cart exists" },
  priority: "high",
  tags: ["smoke"],
  steps: [{ id: "step", position: 1, action: { text: "Pay" }, expected_result: { text: "Approved" } }],
  created_at: "2026-07-14T00:00:00Z",
  created_by_id: null,
} satisfies TTestCase["current"];

const testCase = {
  id: "case",
  sequence: 1,
  folder_id: null,
  current_version: 1,
  archived_at: null,
  created_at: "",
  updated_at: "",
  current: version,
  work_item_ids: [],
  latest_status: null,
} satisfies TTestCase;

const failedRun = {
  id: "run",
  name: "Release smoke",
  description: {},
  status: "active",
  run_type: "fixed",
  build: "1.0.0",
  configuration: {},
  cycle_id: null,
  module_id: null,
  closed_at: null,
  created_at: "",
  updated_at: "",
  progress: { total: 1, open: 0, passed: 0, failed: 1, blocked: 0, skipped: 0 },
  run_cases: [
    {
      id: "run-case",
      test_case_id: "case",
      test_case_version: version,
      position: 1,
      latest_status: "failed",
      results: [
        {
          id: "result",
          sequence: 1,
          status: "failed",
          actual_result: { text: "HTTP 500" },
          duration_ms: 100,
          executed_by_id: null,
          created_at: "",
          defects: [
            {
              id: "issue",
              name: "Checkout defect",
              sequence_id: 12,
              state_group: "completed",
              created_at: "",
            },
          ],
        },
      ],
    },
  ],
} satisfies TTestRun;

const folder = {
  id: "folder",
  name: "Checkout",
  parent_id: null,
  sort_order: 0,
  created_at: "2026-07-14T00:00:00Z",
  updated_at: "2026-07-14T00:00:00Z",
} satisfies TTestFolder;

describe("Testing components", () => {
  it("exposes rename and delete controls for every folder", () => {
    const html = renderToStaticMarkup(
      <FolderTree
        folders={[folder]}
        selectedFolder={null}
        onSelect={vi.fn()}
        onCreate={vi.fn()}
        onRename={vi.fn()}
        onDelete={vi.fn()}
      />
    );
    expect(html).toContain("Checkout");
    expect(html).toContain("Rename Checkout");
    expect(html).toContain("Delete Checkout");
  });

  it("renders selectable pinned cases in the run builder", () => {
    const html = renderToStaticMarkup(<TestRunBuilder testCases={[testCase]} onCancel={vi.fn()} onCreate={vi.fn()} />);
    expect(html).toContain("Checkout succeeds");
    expect(html).toContain("TC-1");
    expect(html).toContain("Create fixed test run");
  });

  it("shows resolved defects as ready for append-only retest", () => {
    const html = renderToStaticMarkup(
      <ExecutionWorkspace
        run={failedRun}
        onBack={vi.fn()}
        onResult={vi.fn()}
        onClose={vi.fn()}
        onCreateDefect={vi.fn()}
      />
    );
    expect(html).toContain("Ready for retest");
    expect(html).toContain("Checkout defect (completed)");
    expect(html).toContain("Pass (P)");
    expect(html).toContain("Fail (F)");
  });

  it("removes mutation controls after a run is closed", () => {
    const html = renderToStaticMarkup(
      <ExecutionWorkspace
        run={{ ...failedRun, status: "completed" }}
        onBack={vi.fn()}
        onResult={vi.fn()}
        onClose={vi.fn()}
        onCreateDefect={vi.fn()}
      />
    );
    expect(html).toContain("Closed");
    expect(html).not.toContain("Pass (P)");
    expect(html).not.toContain("Close run");
  });
});
