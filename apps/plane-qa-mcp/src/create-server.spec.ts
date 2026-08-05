import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { PlaneQAError, type PlaneQAClient } from "@plane/qa-sdk";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createPlaneQAServer } from "./create-server";
import { toolResult } from "./results";

const project = { id: "11111111-1111-4111-8111-111111111111", name: "QA", identifier: "QA", workspace: "acme" };

const connect = async (overrides: Record<string, unknown> = {}) => {
  const plane = {
    resolveProject: vi.fn().mockResolvedValue(project),
    listStates: vi.fn().mockResolvedValue([{ id: "state-1", name: "Open", group: "unstarted" }]),
    getTestingCapabilities: vi.fn().mockResolvedValue({ enabled: true, stage: "production", capabilities: {} }),
    ...overrides,
  } as unknown as PlaneQAClient;
  const server = createPlaneQAServer(plane);
  const client = new Client({ name: "plane-qa-test", version: "1.0.0" });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([server.connect(serverTransport), client.connect(clientTransport)]);
  return { client, plane, server };
};

const connections: Array<Awaited<ReturnType<typeof connect>>> = [];

afterEach(async () => {
  await Promise.all(
    connections.splice(0).map(async ({ client, server }) => {
      await client.close();
      await server.close();
    })
  );
});

describe("Plane QA MCP server", () => {
  it("publishes the integrated project and QA tool surface with safety annotations", async () => {
    const connection = await connect();
    connections.push(connection);
    const response = await connection.client.listTools();

    expect(response.tools.length).toBeGreaterThanOrEqual(30);
    expect(response.tools.map((tool) => tool.name)).toEqual(
      expect.arrayContaining([
        "project_get_context",
        "issue_transition",
        "test_case_update",
        "test_case_attachment_upload",
        "testing_search",
        "testing_export",
        "test_result_create_defect",
        "quality_release_gate",
        "automation_upload_junit",
        "create_work_item_type",
        "create_work_item_property",
        "create_milestone",
        "create_initiative",
      ])
    );
    expect(response.tools.find((tool) => tool.name === "test_folder_delete")?.annotations).toMatchObject({
      destructiveHint: true,
      readOnlyHint: false,
    });
    expect(response.tools.find((tool) => tool.name === "quality_overview")?.annotations).toMatchObject({
      readOnlyHint: true,
      openWorldHint: false,
    });
  });

  it("resolves shared project context and returns structured content", async () => {
    const connection = await connect();
    connections.push(connection);
    const response = await connection.client.callTool({
      name: "project_get_context",
      arguments: { workspace: "acme", project: "QA" },
    });

    expect(response.isError).not.toBe(true);
    expect(response.structuredContent).toMatchObject({ data: { project, states: expect.any(Array) } });
    expect(connection.plane.resolveProject).toHaveBeenCalledWith("acme", "QA");
  });

  it("searches test cases and work items through the shared project scope", async () => {
    const searchTesting = vi.fn().mockResolvedValue({ count: 1, results: [{ identifier: "QA-42" }] });
    const connection = await connect({ searchTesting });
    connections.push(connection);

    const response = await connection.client.callTool({
      name: "testing_search",
      arguments: { workspace: "acme", project: "QA", query: "priority:high payment", search_scope: "all" },
    });

    expect(response.isError).not.toBe(true);
    expect(searchTesting).toHaveBeenCalledWith("acme", project.id, "priority:high payment", "all");
  });

  it("uploads base64 test-case evidence through the SDK", async () => {
    const uploadTestCaseAttachment = vi.fn().mockResolvedValue({ id: "asset" });
    const connection = await connect({ uploadTestCaseAttachment });
    connections.push(connection);

    const response = await connection.client.callTool({
      name: "test_case_attachment_upload",
      arguments: {
        workspace: "acme",
        project: "QA",
        case_id: project.id,
        file_name: "evidence.txt",
        mime_type: "text/plain",
        content_base64: Buffer.from("passed").toString("base64"),
      },
    });

    expect(response.isError).not.toBe(true);
    expect(uploadTestCaseAttachment).toHaveBeenCalledWith(
      "acme",
      project.id,
      project.id,
      expect.objectContaining({ name: "evidence.txt", type: "text/plain", content: expect.any(Blob) })
    );
  });

  it("passes a requirement-kind selection through to the list query", async () => {
    const listIssues = vi.fn().mockResolvedValue({ results: [] });
    const connection = await connect({ listIssues });
    connections.push(connection);

    const response = await connection.client.callTool({
      name: "issue_list",
      arguments: { workspace: "acme", project: "QA", requirement_kind: "functional,quality" },
    });

    expect(response.isError).not.toBe(true);
    expect(listIssues).toHaveBeenCalledWith(
      "acme",
      project.id,
      expect.objectContaining({ requirement_kind: "functional,quality" })
    );
  });

  it("carries the requirement classification through create and update", async () => {
    const createIssue = vi.fn().mockResolvedValue({ id: "i1", sequence_id: 1 });
    const updateIssue = vi.fn().mockResolvedValue({ id: "i1", sequence_id: 34 });
    const resolveIssue = vi.fn().mockResolvedValue({ id: "i1", sequence_id: 34 });
    const connection = await connect({ createIssue, updateIssue, resolveIssue });
    connections.push(connection);

    const created = await connection.client.callTool({
      name: "issue_create",
      arguments: {
        workspace: "acme",
        project: "QA",
        name: "Checkout stays under 2s at peak",
        requirement_kind: "quality",
      },
    });
    const updated = await connection.client.callTool({
      name: "issue_update",
      arguments: { workspace: "acme", project: "QA", issue: "QA-34", requirement_kind: "functional" },
    });

    expect(created.isError).not.toBe(true);
    expect(updated.isError).not.toBe(true);
    expect(createIssue).toHaveBeenCalledWith(
      "acme",
      project.id,
      expect.objectContaining({ requirement_kind: "quality" })
    );
    expect(updateIssue).toHaveBeenCalledWith(
      "acme",
      project.id,
      "i1",
      expect.objectContaining({ requirement_kind: "functional" })
    );
  });

  // A model reaching for `NFR` or `non-functional` should be corrected by the schema rather
  // than by a 400 several seconds later, and the enum is what puts the three legal words in
  // the tool listing where the model reads them before choosing.
  it("rejects a requirement kind outside the closed set before the backend is called", async () => {
    const createIssue = vi.fn();
    const connection = await connect({ createIssue });
    connections.push(connection);

    const response = await connection.client.callTool({
      name: "issue_create",
      arguments: { workspace: "acme", project: "QA", name: "Uptime", requirement_kind: "NFR" },
    });

    expect(response.isError).toBe(true);
    expect(createIssue).not.toHaveBeenCalled();
  });

  it("rejects destructive calls without literal confirmation before the backend is called", async () => {
    const deleteTestFolder = vi.fn();
    const connection = await connect({ deleteTestFolder });
    connections.push(connection);
    const response = await connection.client.callTool({
      name: "test_folder_delete",
      arguments: { workspace: "acme", project: "QA", folder_id: project.id },
    });

    expect(response.isError).toBe(true);
    expect(deleteTestFolder).not.toHaveBeenCalled();
  });

  it("maps backend failures without exposing credentials", async () => {
    const secret = "plane-secret-token";
    const connection = await connect({
      listProjects: vi.fn().mockRejectedValue(
        new PlaneQAError({
          kind: "permission",
          message: "Access denied",
          status: 403,
        })
      ),
    });
    connections.push(connection);
    const response = await connection.client.callTool({
      name: "project_list",
      arguments: { workspace: "acme" },
    });
    const serialized = JSON.stringify(response);

    expect(response.isError).toBe(true);
    expect(serialized).toContain("permission");
    expect(serialized).not.toContain(secret);
  });

  it("bounds both text and structured output", () => {
    const response = toolResult({
      rows: Array.from({ length: 10_000 }, (_, index) => ({ index, value: "x".repeat(40) })),
    });

    expect(response.structuredContent).toMatchObject({ truncated: true });
    expect(response.content[0]?.type === "text" && response.content[0].text.length).toBeLessThan(12_100);
  });
});
