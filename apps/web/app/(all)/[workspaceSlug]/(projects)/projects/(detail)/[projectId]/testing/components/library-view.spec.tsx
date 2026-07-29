import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";
import type { TTestCase, TTestFolder, TTestingSearchResult } from "@plane/types";

const { useTestingMock } = vi.hoisted(() => ({ useTestingMock: vi.fn() }));

vi.mock("@/hooks/store/use-testing", () => ({ useTesting: useTestingMock }));
vi.mock("@/components/core/modals/existing-issues-list-modal", () => ({
  ExistingIssuesListModal: ({ openWorkItemsInNewTab }: { openWorkItemsInNewTab?: boolean }) => (
    <span data-open-work-items-in-new-tab={String(openWorkItemsInNewTab)} />
  ),
}));

import {
  TestCaseExecutionHistory,
  TestCaseTraceability,
  TestLibrarySearchResult,
  TestLibraryView,
} from "./library-view";

const folder = {
  id: "folder",
  name: "Checkout",
  parent_id: null,
  sort_order: 1,
  created_at: "",
  updated_at: "",
} satisfies TTestFolder;

const testCase = {
  id: "case",
  sequence: 1,
  folder_id: "folder",
  current_version: 1,
  archived_at: null,
  created_at: "",
  updated_at: "",
  current: {
    id: "version",
    version: 1,
    title: "Checkout succeeds",
    description: { text: "Validate checkout" },
    preconditions: {},
    priority: "high",
    case_type: "functional",
    tags: ["smoke"],
    steps: [],
    created_at: "",
    created_by_id: null,
  },
  work_item_ids: [],
  work_items: [],
  executions: [],
  latest_status: null,
} satisfies TTestCase;

const testingStore = (cases: Record<string, TTestCase>) => ({
  cases,
  attachments: {},
  folders: { [folder.id]: folder },
  loading: false,
  createCase: vi.fn(),
  updateCase: vi.fn(),
  archiveCase: vi.fn(),
  createFolder: vi.fn(),
  renameFolder: vi.fn(),
  deleteFolder: vi.fn(),
  linkWorkItem: vi.fn(),
  unlinkWorkItem: vi.fn(),
  searchLibrary: vi.fn(),
  exportSearch: vi.fn(),
  fetchAttachments: vi.fn(),
  uploadAttachment: vi.fn(),
  deleteAttachment: vi.fn(),
  exportLibraryCSV: vi.fn(),
  importLibraryCSV: vi.fn(),
});

describe("TestLibraryView", () => {
  it("keeps export formats out of the search controls", () => {
    useTestingMock.mockReturnValue(testingStore({ [testCase.id]: testCase }));

    const html = renderToStaticMarkup(
      <MemoryRouter>
        <TestLibraryView workspaceSlug="workspace" projectId="project" />
      </MemoryRouter>
    );

    expect(html).toContain('aria-label="testing.suites.delete"');
    expect(html).toContain('aria-label="Archive TC-1"');
    expect(html).toContain('aria-label="Search test cases and work items"');
    expect(html).toContain('aria-label="common.export"');
    expect(html).toContain("Controlled query fields");
    expect(html).not.toContain(">XLSX<");
    expect(html).not.toContain(">HTML<");
  });

  it("uses same-tab app links for requirements and execution history", () => {
    const linkedCase = {
      ...testCase,
      work_item_ids: ["issue"],
      work_items: [{ id: "issue", sequence_id: 42, name: "Checkout requirement", state_group: "started" }],
      executions: [
        {
          run_id: "run",
          run_case_id: "run-case",
          run_name: "Release smoke",
          build: "1.0.0",
          run_status: "active",
          pinned_version: 1,
          latest_status: "passed",
          executed_at: "2026-07-29T00:00:00Z",
        },
      ],
      latest_status: "passed",
    } satisfies TTestCase;
    useTestingMock.mockReturnValue(testingStore({ [linkedCase.id]: linkedCase }));

    const html = renderToStaticMarkup(
      <MemoryRouter>
        <TestCaseTraceability
          testCase={linkedCase}
          workspaceSlug="workspace"
          projectId="project"
          onLinkRequirement={vi.fn()}
          onUnlinkWorkItem={vi.fn()}
        />
        <TestCaseExecutionHistory testCase={linkedCase} workspaceSlug="workspace" projectId="project" />
      </MemoryRouter>
    );

    expect(html).toContain('href="/workspace/projects/project/issues/issue"');
    expect(html).toContain('href="/workspace/projects/project/testing/runs/run/run-case"');
    expect(html).not.toContain('target="_blank"');
  });

  it("uses a same-tab app link for work items in library search results", () => {
    const result = {
      kind: "work_item",
      id: "issue",
      identifier: "PROJ-42",
      sequence: 42,
      title: "Checkout requirement",
      description: "",
      preconditions: "",
      steps: "",
      priority: "high",
      status: "started",
      folder: "",
      tags: [],
      linked_record_ids: [],
      linked_records: [],
      updated_at: "2026-07-29T00:00:00Z",
    } satisfies TTestingSearchResult;

    const html = renderToStaticMarkup(
      <MemoryRouter>
        <TestLibrarySearchResult result={result} workspaceSlug="workspace" projectId="project" onOpenCase={vi.fn()} />
      </MemoryRouter>
    );

    expect(html).toContain('href="/workspace/projects/project/issues/issue"');
    expect(html).not.toContain('target="_blank"');
  });

  it("keeps requirement picker previews in the same tab", () => {
    useTestingMock.mockReturnValue(testingStore({ [testCase.id]: testCase }));

    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={["/workspace/projects/project/testing/cases/1"]}>
        <Routes>
          <Route
            path="/:workspaceSlug/projects/:projectId/testing/cases/:sequence"
            element={<TestLibraryView workspaceSlug="workspace" projectId="project" />}
          />
        </Routes>
      </MemoryRouter>
    );

    expect(html).toContain('data-open-work-items-in-new-tab="false"');
  });
});
