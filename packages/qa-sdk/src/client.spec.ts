import { describe, expect, it, vi } from "vitest";

import { PlaneQAClient, PlaneQAError } from "./index";

const jsonResponse = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });

describe("PlaneQAClient", () => {
  it("sends API-key authentication without exposing it in the URL", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse({
        enabled: true,
        stage: "production",
        capabilities: { test_cases: true, test_runs: true, reports: true, automation_ingestion: true },
      })
    );
    const client = new PlaneQAClient({
      baseUrl: "http://plane.local/",
      apiKey: "super-secret",
      fetch: fetcher,
    });

    await client.getTestingCapabilities("sunny", "project-id");

    const [url, init] = fetcher.mock.calls[0] ?? [];
    expect(String(url)).toBe("http://plane.local/api/v1/workspaces/sunny/projects/project-id/testing/capabilities/");
    expect(String(url)).not.toContain("super-secret");
    expect(new Headers(init?.headers).get("X-API-Key")).toBe("super-secret");
  });

  it("retries idempotent reads after a retryable response", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ error: "busy" }, 503))
      .mockResolvedValueOnce(jsonResponse({ results: [] }));
    const client = new PlaneQAClient({
      baseUrl: "http://plane.local",
      apiKey: "token",
      fetch: fetcher,
      retryBaseDelayMs: 0,
    });

    const result = await client.listProjects("sunny");

    expect(result.results).toEqual([]);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("maps safe API failures to stable error categories", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ error: "No membership" }, 403));
    const client = new PlaneQAClient({ baseUrl: "http://plane.local", apiKey: "token", fetch: fetcher });

    const request = client.getProject("sunny", "missing");

    await expect(request).rejects.toMatchObject({
      name: "PlaneQAError",
      kind: "permission",
      status: 403,
      message: "No membership",
      retryable: false,
    } satisfies Partial<PlaneQAError>);
  });

  it("resolves a human project identifier through the project list", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse({
        results: [
          {
            id: "11111111-1111-4111-8111-111111111111",
            identifier: "QA",
            name: "Quality",
            workspace: "workspace-id",
          },
        ],
      })
    );
    const client = new PlaneQAClient({ baseUrl: "http://plane.local", apiKey: "token", fetch: fetcher });

    const project = await client.resolveProject("sunny", "qa");

    expect(project.id).toBe("11111111-1111-4111-8111-111111111111");
  });

  it("rejects malformed critical responses at runtime", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ id: "not-a-project" }));
    const client = new PlaneQAClient({ baseUrl: "http://plane.local", apiKey: "token", fetch: fetcher });

    await expect(client.getProject("sunny", "broken")).rejects.toMatchObject({
      name: "PlaneQAError",
      kind: "server",
    });
  });

  it("marks idempotent automation retries with one stable key", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ error: "temporary" }, 503))
      .mockResolvedValueOnce(jsonResponse({ id: "ingestion-id", replayed: false }, 201));
    const client = new PlaneQAClient({
      baseUrl: "http://plane.local",
      apiKey: "token",
      fetch: fetcher,
      retryBaseDelayMs: 0,
    });

    await client.ingestAutomation("sunny", "project-id", "ci-42", {
      name: "CI 42",
      source: "github-actions",
      format: "results",
      results: [],
    });

    expect(fetcher).toHaveBeenCalledTimes(2);
    for (const [, init] of fetcher.mock.calls) {
      expect(new Headers(init?.headers).get("Idempotency-Key")).toBe("ci-42");
    }
  });

  it("distinguishes issue UUIDs from human identifiers", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockImplementation(async () => jsonResponse({ id: "issue", name: "Issue", sequence_id: 1 }));
    const client = new PlaneQAClient({ baseUrl: "http://plane.local", apiKey: "token", fetch: fetcher });

    await client.resolveIssue("sunny", "project", "11111111-1111-4111-8111-111111111111");
    await client.resolveIssue("sunny", "project", "QA-42");

    expect(String(fetcher.mock.calls[0]?.[0])).toContain(
      "/projects/project/work-items/11111111-1111-4111-8111-111111111111/"
    );
    expect(String(fetcher.mock.calls[1]?.[0])).toContain("/workspaces/sunny/work-items/QA-42/");
  });

  it("targets the CE work-item extension endpoints", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        jsonResponse(
          {
            id: "11111111-1111-4111-8111-111111111111",
            name: "Test case",
            description: "",
            is_epic: false,
            is_default: false,
            is_active: true,
            level: 0,
          },
          201
        )
      )
      .mockResolvedValueOnce(
        jsonResponse(
          {
            id: "22222222-2222-4222-8222-222222222222",
            name: "MVP",
            description: "",
            target_date: null,
            status: "planned",
            sort_order: 65535,
          },
          201
        )
      )
      .mockResolvedValueOnce(
        jsonResponse(
          {
            id: "33333333-3333-4333-8333-333333333333",
            name: "Quality foundation",
            description: "",
            target_date: null,
            status: "planned",
            projects: [],
          },
          201
        )
      );
    const client = new PlaneQAClient({ baseUrl: "http://plane.local", apiKey: "token", fetch: fetcher });

    await client.createWorkItemType("sunny", { name: "Test case" });
    await client.createMilestone("sunny", "project-id", { name: "MVP" });
    await client.createInitiative("sunny", { name: "Quality foundation" });

    expect(String(fetcher.mock.calls[0]?.[0])).toContain("/workspaces/sunny/work-item-types/");
    expect(String(fetcher.mock.calls[1]?.[0])).toContain("/projects/project-id/milestones/");
    expect(String(fetcher.mock.calls[2]?.[0])).toContain("/workspaces/sunny/initiatives/");
  });

  it("searches test cases and work items with the controlled query endpoint", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse({
        query: "priority:high payment",
        scope: "all",
        count: 1,
        results: [{ kind: "work_item", id: "issue", identifier: "QA-42", title: "Payment" }],
      })
    );
    const client = new PlaneQAClient({ baseUrl: "http://plane.local", apiKey: "token", fetch: fetcher });

    const result = await client.searchTesting("sunny", "project", "priority:high payment", "all");

    const url = new URL(String(fetcher.mock.calls[0]?.[0]));
    expect(url.pathname).toContain("/projects/project/testing/search/");
    expect(url.searchParams.get("query")).toBe("priority:high payment");
    expect(result.results[0]?.identifier).toBe("QA-42");
  });

  it("preserves binary XLSX exports", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(new Uint8Array([80, 75, 3, 4]), {
        headers: { "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" },
      })
    );
    const client = new PlaneQAClient({ baseUrl: "http://plane.local", apiKey: "token", fetch: fetcher });

    const result = await client.exportTesting("sunny", "project", "tag:smoke", "test_cases", "excel");

    expect(result).toEqual(new Uint8Array([80, 75, 3, 4]));
    const url = new URL(String(fetcher.mock.calls[0]?.[0]));
    expect(url.searchParams.get("export_format")).toBe("excel");
  });

  it("uploads a test case attachment and confirms it before returning", async () => {
    const attachment = {
      id: "asset-id",
      attributes: { name: "evidence.png", type: "image/png", size: 3 },
      size: 3,
      created_at: "",
      created_by_id: null,
      download_url: "/download",
      preview_url: "/preview",
    };
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        jsonResponse({
          asset_id: "asset-id",
          asset_url: "/download",
          upload_data: { url: "https://storage.example/upload", fields: { key: "object-key" } },
          attachment,
        })
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    const client = new PlaneQAClient({ baseUrl: "http://plane.local", apiKey: "token", fetch: fetcher });

    const result = await client.uploadTestCaseAttachment("sunny", "project", "case", {
      name: "evidence.png",
      type: "image/png",
      content: new Blob([new Uint8Array([1, 2, 3])], { type: "image/png" }),
    });

    expect(result.id).toBe("asset-id");
    expect(String(fetcher.mock.calls[1]?.[0])).toBe("https://storage.example/upload");
    expect(new Headers(fetcher.mock.calls[1]?.[1]?.headers).has("X-API-Key")).toBe(false);
    expect(String(fetcher.mock.calls[2]?.[0])).toContain("/attachments/asset-id/");
    expect(fetcher.mock.calls[2]?.[1]?.method).toBe("PATCH");
  });
});
