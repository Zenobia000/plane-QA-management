import { renderToStaticMarkup } from "react-dom/server";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { initPromise } from "@plane/i18n";
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
  // The components read their copy through i18n now, so the English bundle has to
  // be resolved before a static render can be asserted on.
  //
  // Assertions deliberately avoid interpolated copy. ICU interpolation does not
  // run under vitest -- pre-existing keys such as `entity.delete.label` come back
  // as "Delete {entity}" here too -- so a placeholder surviving in this output
  // says nothing about the browser. Nothing in this suite can catch a broken
  // interpolation; only a rendered check can.
  beforeAll(async () => {
    await initPromise;
  });

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
    expect(html).toContain('aria-label="Rename');
    expect(html).toContain('aria-label="Delete');
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
        onSelectRunCase={vi.fn()}
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

  it("shows the addressed run case rather than the first open one", () => {
    const twoCaseRun = {
      ...failedRun,
      run_cases: [
        { ...failedRun.run_cases[0], id: "run-case-open", latest_status: "open", results: [], position: 1 },
        { ...failedRun.run_cases[0], id: "run-case-addressed", position: 2 },
      ],
    } satisfies TTestRun;
    const html = renderToStaticMarkup(
      <ExecutionWorkspace
        run={twoCaseRun}
        selectedRunCaseId="run-case-addressed"
        onSelectRunCase={vi.fn()}
        onBack={vi.fn()}
        onResult={vi.fn()}
        onClose={vi.fn()}
        onCreateDefect={vi.fn()}
      />
    );
    // The defect panel renders only for the addressed case, so its presence is
    // what proves the URL won over the first-open default.
    expect(html).toContain("Checkout defect (completed)");
  });

  it("falls back to the first open case when the URL addresses none", () => {
    const twoCaseRun = {
      ...failedRun,
      run_cases: [
        { ...failedRun.run_cases[0], id: "run-case-open", latest_status: "open", results: [], position: 1 },
        { ...failedRun.run_cases[0], id: "run-case-failed", position: 2 },
      ],
    } satisfies TTestRun;
    const html = renderToStaticMarkup(
      <ExecutionWorkspace
        run={twoCaseRun}
        onSelectRunCase={vi.fn()}
        onBack={vi.fn()}
        onResult={vi.fn()}
        onClose={vi.fn()}
        onCreateDefect={vi.fn()}
      />
    );
    expect(html).not.toContain("Checkout defect (completed)");
  });

  it("removes mutation controls after a run is closed", () => {
    const html = renderToStaticMarkup(
      <ExecutionWorkspace
        run={{ ...failedRun, status: "completed" }}
        onSelectRunCase={vi.fn()}
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
