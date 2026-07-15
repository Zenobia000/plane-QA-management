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
});
