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
