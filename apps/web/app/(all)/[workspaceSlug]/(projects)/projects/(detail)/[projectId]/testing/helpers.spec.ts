import { describe, expect, it } from "vitest";
import type { TTestCase } from "@plane/types";
import { findCaseBySequence, formatScenario, parseScenario, testingPath } from "./helpers";

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
      case_type: "functional",
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

describe("scenario text", () => {
  it("splits Given from the When/Then pairs", () => {
    const parsed = parseScenario(
      ["Given the user is signed in", "When they export orders", "Then a download link appears"].join("\n")
    );

    expect(parsed.preconditions).toBe("the user is signed in");
    expect(parsed.steps).toEqual([{ action: "they export orders", expected_result: "a download link appears" }]);
  });

  it("opens a new step at every When", () => {
    const parsed = parseScenario(
      ["When they pay", "Then the order confirms", "When they refund", "Then the balance returns"].join("\n")
    );

    expect(parsed.steps.map((s) => s.action)).toEqual(["they pay", "they refund"]);
    expect(parsed.steps.map((s) => s.expected_result)).toEqual(["the order confirms", "the balance returns"]);
  });

  it("continues the last keyword through And and But", () => {
    const parsed = parseScenario(
      [
        "Given a 3DS-enrolled card",
        "And a cart over the limit",
        "When they submit",
        "And they complete the challenge",
        "Then the order confirms",
        "But no second charge is made",
      ].join("\n")
    );

    expect(parsed.preconditions).toBe("a 3DS-enrolled card\na cart over the limit");
    expect(parsed.steps[0].action).toBe("they submit\nthey complete the challenge");
    expect(parsed.steps[0].expected_result).toBe("the order confirms\nno second charge is made");
  });

  it("keeps a line that carries no keyword", () => {
    // Pasted prose must survive; dropping it loses what someone actually wrote.
    const parsed = parseScenario(["When they submit", "with a 5,000-row file", "Then it completes"].join("\n"));

    expect(parsed.steps[0].action).toBe("they submit\nwith a 5,000-row file");
  });

  it("treats text before any keyword as setup", () => {
    const parsed = parseScenario(
      ["The reporting service is up", "When they open the page", "Then it renders"].join("\n")
    );

    expect(parsed.preconditions).toBe("The reporting service is up");
    expect(parsed.steps).toHaveLength(1);
  });

  it("gives a stray Then somewhere to live", () => {
    const parsed = parseScenario("Then the page loads");

    expect(parsed.steps).toEqual([{ action: "", expected_result: "the page loads" }]);
  });

  it("round-trips through the stored shape", () => {
    const text = [
      "Given a 3DS-enrolled card",
      "And a cart over the limit",
      "When they submit",
      "Then the order confirms",
      "When they refund",
      "Then the balance returns",
    ].join("\n");

    const parsed = parseScenario(text);

    expect(formatScenario(parsed.preconditions, parsed.steps)).toBe(text);
  });

  it("renders a case written before this editor existed", () => {
    expect(formatScenario("logged in", [{ action: "click export", expected_result: "file downloads" }])).toBe(
      ["Given logged in", "When click export", "Then file downloads"].join("\n")
    );
  });

  it("ignores blank lines rather than making empty steps", () => {
    const parsed = parseScenario("Given x\n\n\nWhen y\n\nThen z\n");

    expect(parsed.steps).toHaveLength(1);
    expect(parsed.preconditions).toBe("x");
  });
});
