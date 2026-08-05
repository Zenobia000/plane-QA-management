import type { PlaneQAClient } from "@plane/qa-sdk";
import { describe, expect, it, vi } from "vitest";

import { runCLI } from "./run";

const environment = {
  PLANE_URL: "http://plane.local",
  PLANE_API_KEY: "never-print-this-token",
  PLANE_WORKSPACE: "sunny",
  PLANE_PROJECT: "QA",
};

const capture = () => {
  const stdout: string[] = [];
  const stderr: string[] = [];
  return {
    stdout,
    stderr,
    io: {
      stdout: (value: string) => stdout.push(value),
      stderr: (value: string) => stderr.push(value),
    },
  };
};

describe("plane-qa CLI", () => {
  it("prints help without credentials", async () => {
    const output = capture();

    const code = await runCLI({ argv: ["--help"], environment: {}, io: output.io });

    expect(code).toBe(0);
    expect(output.stdout.join("")).toContain("project list|get|update|states");
  });

  it("prints project data as JSON only", async () => {
    const output = capture();
    const listProjects = vi.fn().mockResolvedValue({ results: [{ id: "p1", identifier: "QA" }] });
    const client = { listProjects } as unknown as PlaneQAClient;

    const code = await runCLI({
      argv: ["project", "list"],
      environment,
      io: output.io,
      createClient: () => client,
    });

    expect(code).toBe(0);
    expect(JSON.parse(output.stdout.join(""))).toEqual({ results: [{ id: "p1", identifier: "QA" }] });
    expect(output.stderr).toEqual([]);
    expect(output.stdout.join("")).not.toContain(environment.PLANE_API_KEY);
  });

  it("passes --leaf-only through as a boolean so agents see the same list as the UI", async () => {
    const output = capture();
    const listIssues = vi.fn().mockResolvedValue({ results: [] });
    const resolveProject = vi.fn().mockResolvedValue({ id: "p1", identifier: "QA" });
    const client = { listIssues, resolveProject } as unknown as PlaneQAClient;

    const code = await runCLI({
      argv: ["issue", "list", "--leaf-only"],
      environment,
      io: output.io,
      createClient: () => client,
    });

    expect(code).toBe(0);
    expect(listIssues).toHaveBeenCalledWith("sunny", "p1", expect.objectContaining({ leaf_only: true }));
  });

  it("omits leaf_only entirely when the flag is absent, leaving the server default", async () => {
    const output = capture();
    const listIssues = vi.fn().mockResolvedValue({ results: [] });
    const resolveProject = vi.fn().mockResolvedValue({ id: "p1", identifier: "QA" });
    const client = { listIssues, resolveProject } as unknown as PlaneQAClient;

    await runCLI({ argv: ["issue", "list"], environment, io: output.io, createClient: () => client });

    expect(listIssues).toHaveBeenCalledWith(
      "sunny",
      "p1",
      expect.not.objectContaining({ leaf_only: expect.anything() })
    );
  });

  it("filters the list by requirement kind, including a union of kinds", async () => {
    const output = capture();
    const listIssues = vi.fn().mockResolvedValue({ results: [] });
    const client = {
      listIssues,
      resolveProject: vi.fn().mockResolvedValue({ id: "p1", identifier: "QA" }),
    } as unknown as PlaneQAClient;

    await runCLI({
      argv: ["issue", "list", "--requirement-kind", "functional,quality"],
      environment,
      io: output.io,
      createClient: () => client,
    });

    expect(listIssues).toHaveBeenCalledWith(
      "sunny",
      "p1",
      expect.objectContaining({ requirement_kind: "functional,quality" })
    );
  });

  // A filter given a kind the server does not know matches nothing, so the mistake comes back
  // as an empty list that reads like a true answer. Worth catching before the request.
  it("rejects an unknown kind in a list filter rather than returning an empty answer", async () => {
    const output = capture();
    const listIssues = vi.fn();
    const client = {
      listIssues,
      resolveProject: vi.fn().mockResolvedValue({ id: "p1", identifier: "QA" }),
    } as unknown as PlaneQAClient;

    const code = await runCLI({
      argv: ["issue", "list", "--requirement-kind", "quality,NFR"],
      environment,
      io: output.io,
      createClient: () => client,
    });

    expect(code).not.toBe(0);
    expect(listIssues).not.toHaveBeenCalled();
    expect(output.stderr.join("")).toContain("none, functional, quality");
  });

  it("classifies a work item as a quality requirement on create", async () => {
    const output = capture();
    const createIssue = vi.fn().mockResolvedValue({ id: "i1", sequence_id: 1 });
    const client = {
      createIssue,
      resolveProject: vi.fn().mockResolvedValue({ id: "p1", identifier: "QA" }),
    } as unknown as PlaneQAClient;

    const code = await runCLI({
      argv: ["issue", "create", "--name", "Checkout stays under 2s at peak", "--requirement-kind", "quality"],
      environment,
      io: output.io,
      createClient: () => client,
    });

    expect(code).toBe(0);
    expect(createIssue).toHaveBeenCalledWith("sunny", "p1", expect.objectContaining({ requirement_kind: "quality" }));
  });

  it("reclassifies an existing work item on update", async () => {
    const output = capture();
    const updateIssue = vi.fn().mockResolvedValue({ id: "i1", sequence_id: 1 });
    const client = {
      updateIssue,
      resolveProject: vi.fn().mockResolvedValue({ id: "p1", identifier: "QA" }),
      resolveIssue: vi.fn().mockResolvedValue({ id: "i1", sequence_id: 34 }),
    } as unknown as PlaneQAClient;

    const code = await runCLI({
      argv: ["issue", "update", "--issue", "QA-34", "--requirement-kind", "functional"],
      environment,
      io: output.io,
      createClient: () => client,
    });

    expect(code).toBe(0);
    expect(updateIssue).toHaveBeenCalledWith(
      "sunny",
      "p1",
      "i1",
      expect.objectContaining({ requirement_kind: "functional" })
    );
  });

  // Absent must mean "leave it alone" rather than "set it to none": `none` is a real
  // classification meaning "not a requirement", so sending it by default would silently
  // declassify every requirement touched by an unrelated rename.
  it("omits requirement_kind entirely when the flag is absent", async () => {
    const output = capture();
    const updateIssue = vi.fn().mockResolvedValue({ id: "i1", sequence_id: 1 });
    const client = {
      updateIssue,
      resolveProject: vi.fn().mockResolvedValue({ id: "p1", identifier: "QA" }),
      resolveIssue: vi.fn().mockResolvedValue({ id: "i1", sequence_id: 34 }),
    } as unknown as PlaneQAClient;

    await runCLI({
      argv: ["issue", "update", "--issue", "QA-34", "--name", "Renamed"],
      environment,
      io: output.io,
      createClient: () => client,
    });

    expect(updateIssue).toHaveBeenCalledWith(
      "sunny",
      "p1",
      "i1",
      expect.not.objectContaining({ requirement_kind: expect.anything() })
    );
  });

  it("names the three legal kinds when given a near miss, without calling the backend", async () => {
    const output = capture();
    const createIssue = vi.fn();
    const client = {
      createIssue,
      resolveProject: vi.fn().mockResolvedValue({ id: "p1", identifier: "QA" }),
    } as unknown as PlaneQAClient;

    const code = await runCLI({
      argv: ["issue", "create", "--name", "Uptime", "--requirement-kind", "NFR"],
      environment,
      io: output.io,
      createClient: () => client,
    });

    expect(code).not.toBe(0);
    expect(createIssue).not.toHaveBeenCalled();
    expect(output.stderr.join("")).toContain("none, functional, quality");
  });

  it("sends a complete threshold on case create", async () => {
    const output = capture();
    const createTestCase = vi.fn().mockResolvedValue({ id: "c1" });
    const client = {
      createTestCase,
      resolveProject: vi.fn().mockResolvedValue({ id: "p1", identifier: "QA" }),
    } as unknown as PlaneQAClient;

    const code = await runCLI({
      argv: [
        "case",
        "create",
        "--title",
        "Checkout stays under 2s at peak",
        "--case-type",
        "performance",
        "--threshold-metric",
        "checkout P95 latency",
        "--threshold-operator",
        "lt",
        "--threshold-value",
        "2",
        "--threshold-unit",
        "s",
      ],
      environment,
      io: output.io,
      createClient: () => client,
    });

    expect(code).toBe(0);
    expect(createTestCase).toHaveBeenCalledWith(
      "sunny",
      "p1",
      expect.objectContaining({
        case_type: "performance",
        threshold_metric: "checkout P95 latency",
        threshold_operator: "lt",
        threshold_value: 2,
        threshold_unit: "s",
      })
    );
  });

  // All four go together or none do. A lone flag reaching the server as a partial threshold
  // would be rejected there, with a message about a field the caller did not think they were
  // touching.
  it("fills in the rest of the threshold when only some of it is given", async () => {
    const output = capture();
    const createTestCase = vi.fn().mockResolvedValue({ id: "c1" });
    const client = {
      createTestCase,
      resolveProject: vi.fn().mockResolvedValue({ id: "p1", identifier: "QA" }),
    } as unknown as PlaneQAClient;

    await runCLI({
      argv: ["case", "create", "--title", "Uptime", "--threshold-unit", "s"],
      environment,
      io: output.io,
      createClient: () => client,
    });

    expect(createTestCase).toHaveBeenCalledWith(
      "sunny",
      "p1",
      expect.objectContaining({
        threshold_metric: "",
        threshold_operator: "",
        threshold_value: null,
        threshold_unit: "s",
      })
    );
  });

  it("omits the threshold entirely when no threshold flag is given", async () => {
    const output = capture();
    const updateTestCase = vi.fn().mockResolvedValue({ id: "c1" });
    const client = {
      updateTestCase,
      resolveProject: vi.fn().mockResolvedValue({ id: "p1", identifier: "QA" }),
    } as unknown as PlaneQAClient;

    await runCLI({
      argv: ["case", "update", "--case", "c1", "--title", "Renamed"],
      environment,
      io: output.io,
      createClient: () => client,
    });

    expect(updateTestCase).toHaveBeenCalledWith(
      "sunny",
      "p1",
      "c1",
      expect.not.objectContaining({ threshold_metric: expect.anything() })
    );
  });

  it("rejects an operator outside the set, naming the four", async () => {
    const output = capture();
    const createTestCase = vi.fn();
    const client = {
      createTestCase,
      resolveProject: vi.fn().mockResolvedValue({ id: "p1", identifier: "QA" }),
    } as unknown as PlaneQAClient;

    const code = await runCLI({
      argv: ["case", "create", "--title", "Uptime", "--threshold-operator", "<"],
      environment,
      io: output.io,
      createClient: () => client,
    });

    expect(code).not.toBe(0);
    expect(createTestCase).not.toHaveBeenCalled();
    expect(output.stderr.join("")).toContain("lt, lte, gt, gte");
  });

  it("refuses destructive commands without explicit confirmation", async () => {
    const output = capture();
    const client = {
      resolveProject: vi.fn().mockResolvedValue({ id: "p1", identifier: "QA" }),
      getTestCase: vi.fn().mockResolvedValue({ id: "case-1" }),
      archiveTestCase: vi.fn(),
    } as unknown as PlaneQAClient;

    const code = await runCLI({
      argv: ["case", "archive", "--case", "case-1"],
      environment,
      io: output.io,
      createClient: () => client,
    });

    expect(code).toBe(7);
    expect(client.archiveTestCase).not.toHaveBeenCalled();
    expect(JSON.parse(output.stderr.join(""))).toMatchObject({ error: { code: 7 } });
  });

  it("executes a confirmed archive and returns a receipt", async () => {
    const output = capture();
    const archiveTestCase = vi.fn().mockResolvedValue(undefined);
    const client = {
      resolveProject: vi.fn().mockResolvedValue({ id: "p1", identifier: "QA" }),
      archiveTestCase,
    } as unknown as PlaneQAClient;

    const code = await runCLI({
      argv: ["case", "archive", "--case", "case-1", "--yes"],
      environment,
      io: output.io,
      createClient: () => client,
    });

    expect(code).toBe(0);
    expect(archiveTestCase).toHaveBeenCalledWith("sunny", "p1", "case-1");
    expect(JSON.parse(output.stdout.join(""))).toEqual({ archived: true, id: "case-1" });
  });

  it("previews destructive operations with --dry-run and performs no write", async () => {
    const output = capture();
    const archiveTestCase = vi.fn();
    const client = {
      resolveProject: vi.fn().mockResolvedValue({ id: "p1", identifier: "QA" }),
      getTestCase: vi.fn().mockResolvedValue({ id: "case-1" }),
      archiveTestCase,
    } as unknown as PlaneQAClient;

    const code = await runCLI({
      argv: ["case", "archive", "--case", "case-1", "--dry-run"],
      environment,
      io: output.io,
      createClient: () => client,
    });

    expect(code).toBe(0);
    expect(archiveTestCase).not.toHaveBeenCalled();
    expect(JSON.parse(output.stdout.join(""))).toMatchObject({ dry_run: true, operation: "test case archive" });
  });

  it("accepts explicit TTY confirmation", async () => {
    const output = capture();
    const archiveTestCase = vi.fn();
    const client = {
      resolveProject: vi.fn().mockResolvedValue({ id: "p1", identifier: "QA" }),
      getTestCase: vi.fn().mockResolvedValue({ id: "case-1" }),
      archiveTestCase,
    } as unknown as PlaneQAClient;

    const code = await runCLI({
      argv: ["case", "archive", "--case", "case-1"],
      environment,
      io: output.io,
      createClient: () => client,
      confirm: vi.fn().mockResolvedValue(true),
    });

    expect(code).toBe(0);
    expect(archiveTestCase).toHaveBeenCalledOnce();
  });

  it("never echoes a missing or configured API key in errors", async () => {
    const output = capture();
    const client = {
      listProjects: vi.fn().mockRejectedValue(new Error("request failed")),
    } as unknown as PlaneQAClient;

    const code = await runCLI({
      argv: ["project", "list"],
      environment,
      io: output.io,
      createClient: () => client,
    });

    expect(code).toBe(2);
    expect(output.stderr.join("")).not.toContain(environment.PLANE_API_KEY);
  });

  it("creates a project milestone through the extension client contract", async () => {
    const output = capture();
    const createMilestone = vi.fn().mockResolvedValue({ id: "milestone-1", name: "MVP" });
    const client = {
      resolveProject: vi.fn().mockResolvedValue({ id: "p1", identifier: "QA" }),
      createMilestone,
    } as unknown as PlaneQAClient;

    const code = await runCLI({
      argv: ["milestone", "create", "--name", "MVP"],
      environment,
      io: output.io,
      createClient: () => client,
    });

    expect(code).toBe(0);
    expect(createMilestone).toHaveBeenCalledWith("sunny", "p1", { name: "MVP" });
  });

  it("searches across testing and work items with the controlled query", async () => {
    const output = capture();
    const searchTesting = vi.fn().mockResolvedValue({ count: 0, results: [] });
    const client = {
      resolveProject: vi.fn().mockResolvedValue({ id: "p1", identifier: "QA" }),
      searchTesting,
    } as unknown as PlaneQAClient;

    const code = await runCLI({
      argv: ["search", "query", "--query", "priority:high payment", "--scope", "all"],
      environment,
      io: output.io,
      createClient: () => client,
    });

    expect(code).toBe(0);
    expect(searchTesting).toHaveBeenCalledWith("sunny", "p1", "priority:high payment", "all");
  });

  it("uploads a local file as test-case evidence", async () => {
    const output = capture();
    const uploadTestCaseAttachment = vi.fn().mockResolvedValue({ id: "asset" });
    const client = {
      resolveProject: vi.fn().mockResolvedValue({ id: "p1", identifier: "QA" }),
      uploadTestCaseAttachment,
    } as unknown as PlaneQAClient;

    const code = await runCLI({
      argv: [
        "case",
        "attach",
        "--case",
        "case-1",
        "--file",
        "src/fixtures/automation-results.json",
        "--mime-type",
        "text/plain",
      ],
      environment,
      io: output.io,
      createClient: () => client,
    });

    expect(code).toBe(0);
    expect(uploadTestCaseAttachment).toHaveBeenCalledWith(
      "sunny",
      "p1",
      "case-1",
      expect.objectContaining({ name: "automation-results.json", type: "text/plain" })
    );
  });
});
