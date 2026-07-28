import { describe, expect, it } from "vitest";
import type { TTestCase } from "@plane/types";
import { findCaseBySequence, testingPath } from "./helpers";

const makeCase = (id: string, sequence: number) =>
  ({
    id,
    sequence,
    folder_id: null,
    current_version: 1,
    archived_at: null,
    created_at: "",
    updated_at: "",
    current: {
      id: `${id}-v1`,
      version: 1,
      title: `Case ${sequence}`,
      description: {},
      preconditions: {},
      priority: "none",
      tags: [],
      steps: [],
      created_at: "",
      created_by_id: null,
    },
    work_item_ids: [],
    work_items: [],
    executions: [],
    latest_status: null,
  }) satisfies TTestCase;

const cases = {
  a: makeCase("a", 1),
  b: makeCase("b", 12),
};

describe("findCaseBySequence", () => {
  it("resolves the human-readable sequence to its case", () => {
    expect(findCaseBySequence(cases, "12")?.id).toBe("b");
  });

  it("returns undefined for a sequence nothing matches", () => {
    expect(findCaseBySequence(cases, "999")).toBeUndefined();
  });

  it("returns undefined for a non-numeric or missing param rather than throwing", () => {
    expect(findCaseBySequence(cases, "not-a-number")).toBeUndefined();
    expect(findCaseBySequence(cases, undefined)).toBeUndefined();
    expect(findCaseBySequence(cases, "")).toBeUndefined();
  });

  it("does not coerce a decimal or padded sequence into a match", () => {
    expect(findCaseBySequence(cases, "12.0")).toBeUndefined();
    expect(findCaseBySequence(cases, " 12")).toBeUndefined();
  });
});

describe("testingPath", () => {
  const base = { workspaceSlug: "acme", projectId: "proj" };

  it("builds each addressable testing route", () => {
    expect(testingPath({ ...base })).toBe("/acme/projects/proj/testing");
    expect(testingPath({ ...base, tab: "cases" })).toBe("/acme/projects/proj/testing/cases");
    expect(testingPath({ ...base, tab: "cases", sequence: 12 })).toBe("/acme/projects/proj/testing/cases/12");
    expect(testingPath({ ...base, tab: "runs", runId: "r1" })).toBe("/acme/projects/proj/testing/runs/r1");
    expect(testingPath({ ...base, tab: "runs", runId: "r1", runCaseId: "rc1" })).toBe(
      "/acme/projects/proj/testing/runs/r1/rc1"
    );
  });

  it("appends the folder filter only when one is selected", () => {
    expect(testingPath({ ...base, tab: "cases", folderId: "f1" })).toBe("/acme/projects/proj/testing/cases?folder=f1");
    expect(testingPath({ ...base, tab: "cases", folderId: null })).toBe("/acme/projects/proj/testing/cases");
  });

  it("ignores a run case without its run, since the deeper segment cannot stand alone", () => {
    expect(testingPath({ ...base, tab: "runs", runCaseId: "rc1" })).toBe("/acme/projects/proj/testing/runs");
  });
});
