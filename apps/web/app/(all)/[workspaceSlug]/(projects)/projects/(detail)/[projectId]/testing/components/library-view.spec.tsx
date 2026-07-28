import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import type { TTestCase, TTestFolder } from "@plane/types";

const { useTestingMock } = vi.hoisted(() => ({ useTestingMock: vi.fn() }));

vi.mock("@/hooks/store/use-testing", () => ({ useTesting: useTestingMock }));

import { TestLibraryView } from "./library-view";

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

describe("TestLibraryView", () => {
  it("exposes folder deletion and test case archival controls", () => {
    useTestingMock.mockReturnValue({
      cases: { [testCase.id]: testCase },
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

    const html = renderToStaticMarkup(
      <MemoryRouter>
        <TestLibraryView workspaceSlug="workspace" projectId="project" />
      </MemoryRouter>
    );

    expect(html).toContain('aria-label="testing.suites.delete"');
    expect(html).toContain('aria-label="Archive TC-1"');
    expect(html).toContain('aria-label="Search test cases and work items"');
    expect(html).toContain("Controlled query fields");
  });
});
