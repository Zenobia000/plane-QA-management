import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import type { TTestCase } from "@plane/types";

vi.mock("@plane/services", () => ({
  TestingService: class {
    getWorkItemTestCases = vi.fn().mockResolvedValue([]);
  },
}));

import { TestingWorkItemSummaryContent } from "./testing-summary";

const testCase = {
  id: "case",
  sequence: 7,
  folder_id: null,
  current_version: 1,
  archived_at: null,
  created_at: "",
  updated_at: "",
  current: {
    id: "version",
    version: 1,
    title: "Checkout succeeds",
    description: {},
    preconditions: {},
    priority: "high",
    case_type: "functional",
    tags: [],
    steps: [],
    created_at: "",
    created_by_id: null,
  },
  work_item_ids: ["issue"],
  work_items: [],
  executions: [],
  latest_status: "passed",
} satisfies TTestCase;

describe("TestingWorkItemSummaryContent", () => {
  it("uses same-tab app links for Testing and linked test cases", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <TestingWorkItemSummaryContent workspaceSlug="workspace" projectId="project" cases={[testCase]} />
      </MemoryRouter>
    );

    expect(html).toContain('href="/workspace/projects/project/testing"');
    expect(html).toContain('href="/workspace/projects/project/testing/cases/7"');
    expect(html).not.toContain('target="_blank"');
  });

  it("uses a same-tab app link from empty coverage to the test library", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <TestingWorkItemSummaryContent workspaceSlug="workspace" projectId="project" cases={[]} />
      </MemoryRouter>
    );

    expect(html).toContain('href="/workspace/projects/project/testing/cases"');
    expect(html).not.toContain('target="_blank"');
  });
});
