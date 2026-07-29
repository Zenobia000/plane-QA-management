import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { TTestCase, TTestFolder, TTestRun } from "@plane/types";

// react-markdown's transitive mdast packages are browser-bundled in the app but
// expose incompatible named exports under this suite's Node-only SSR runner.
// The workspace contract here is that result text is passed to the renderer;
// markdown rendering itself is covered by that shared component's package.
vi.mock("@/components/ui/markdown-to-component", () => ({
  MarkdownRenderer: ({ markdown }: { markdown: string }) => <>{markdown}</>,
}));

import { ExecutionWorkspace, isEvidenceTypingTarget, uploadResultEvidence } from "./execution-workspace";
import { FolderTree } from "./folder-tree";
import { TestRunBuilder } from "./run-builder";

const version = {
  id: "version",
  version: 1,
  title: "Checkout succeeds",
  description: {},
  preconditions: { text: "A cart exists" },
  priority: "high",
  case_type: "functional",
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
  work_items: [],
  executions: [],
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
    expect(html).toContain('aria-label="testing.suites.rename"');
    expect(html).toContain('aria-label="testing.suites.delete"');
  });

  it("renders selectable pinned cases in the run builder", () => {
    const html = renderToStaticMarkup(
      <TestRunBuilder
        workspaceSlug="acme"
        projectId="project"
        testCases={[testCase]}
        folders={[]}
        onCancel={vi.fn()}
        onCreate={vi.fn()}
      />
    );
    expect(html).toContain("Checkout succeeds");
    expect(html).toContain("TC-1");
    expect(html).toContain("testing.runs.builder_heading");
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
        onListAttachments={vi.fn().mockResolvedValue([])}
        onAttach={vi.fn()}
        onDetach={vi.fn()}
      />
    );
    expect(html).toContain("testing.execution.ready_for_retest");
    expect(html).toContain("Checkout defect (completed)");
    expect(html).toContain("testing.execution.markdown_hint");
    expect(html).toContain("testing.execution.drop_files");
    expect(html).toContain("testing.execution.defect_heading");
    expect(html).toContain("HTTP 500");
    expect(html).toContain("testing.execution.pass");
    expect(html).toContain("testing.execution.fail");
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
        onListAttachments={vi.fn().mockResolvedValue([])}
        onAttach={vi.fn()}
        onDetach={vi.fn()}
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
        onListAttachments={vi.fn().mockResolvedValue([])}
        onAttach={vi.fn()}
        onDetach={vi.fn()}
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
        onListAttachments={vi.fn().mockResolvedValue([])}
        onAttach={vi.fn()}
        onDetach={vi.fn()}
      />
    );
    expect(html).toContain("testing.execution.closed");
    expect(html).not.toContain("testing.execution.pass");
    expect(html).not.toContain("testing.execution.close_run");
  });

  it("keeps append-only result shortcuts inert inside evidence editors", () => {
    expect(isEvidenceTypingTarget({ tagName: "TEXTAREA" } as unknown as EventTarget)).toBe(true);
    expect(
      isEvidenceTypingTarget({
        tagName: "DIV",
        isContentEditable: true,
      } as unknown as EventTarget)
    ).toBe(true);
    expect(
      isEvidenceTypingTarget({
        tagName: "SPAN",
        closest: (selector: string) => (selector.includes("data-evidence-editor") ? {} : null),
      } as unknown as EventTarget)
    ).toBe(true);
    expect(isEvidenceTypingTarget({ tagName: "BUTTON", closest: () => null } as unknown as EventTarget)).toBe(false);
  });

  it("keeps failed evidence files retryable without losing successful uploads", async () => {
    const files = [
      { id: "image", file: { name: "screen.png" } as File, status: "pending" },
      { id: "log", file: { name: "console.log" } as File, status: "pending" },
    ] as const;
    const attached = {
      id: "asset",
      name: "screen.png",
      type: "image/png",
      size: 100,
      asset_url: "https://example.com/screen.png",
      created_at: "",
    };

    const outcome = await uploadResultEvidence([...files], async (item) => {
      if (item.id === "log") throw new Error("storage unavailable");
      return attached;
    });

    expect(outcome.uploaded).toEqual([attached]);
    expect(outcome.failed.map((item) => item.id)).toEqual(["log"]);
  });
});
