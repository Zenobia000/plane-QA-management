/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TTestCase } from "@plane/types";

export type TTestingTab = "overview" | "cases" | "runs";

/**
 * Test cases are addressed by their project-scoped sequence -- the TC-12 a
 * person reads on screen -- rather than by UUID, so URLs stay shareable.
 */
export const findCaseBySequence = (cases: Record<string, TTestCase>, sequence: string | undefined) => {
  if (!sequence || !/^\d+$/.test(sequence)) return undefined;
  const value = Number(sequence);
  return Object.values(cases).find((item) => item.sequence === value);
};

type TTestingPath = {
  workspaceSlug: string;
  projectId: string;
  tab?: TTestingTab;
  sequence?: number;
  runId?: string;
  runCaseId?: string;
  folderId?: string | null;
};

export const testingPath = ({ workspaceSlug, projectId, tab, sequence, runId, runCaseId, folderId }: TTestingPath) => {
  const segments = [`/${workspaceSlug}/projects/${projectId}/testing`];
  if (tab) segments.push(tab);
  if (tab === "cases" && sequence !== undefined) segments.push(String(sequence));
  // A run case is only addressable underneath its run; without one the deeper
  // segment would produce a route that cannot resolve.
  if (tab === "runs" && runId) {
    segments.push(runId);
    if (runCaseId) segments.push(runCaseId);
  }
  const path = segments.join("/");
  return folderId ? `${path}?folder=${folderId}` : path;
};

/**
 * Gherkin in, the stored shape out.
 *
 * A case is stored as `preconditions` plus a list of `(action, expected_result)` pairs, and
 * that has to stay: the execution workspace reads the three parts separately so a tester
 * sees setup, action and expectation as distinct things while running; the CSV export and
 * the auto-built defect description depend on the same split. What was wrong was the
 * *input* -- two boxes, the second demanding `action | expected` on each line, a syntax that
 * existed only because the storage did. Nobody writes a test that way; they write Given /
 * When / Then.
 *
 * The mapping is the obvious one. Given builds the preconditions. Each When opens a step and
 * the Then that follows closes it. And/But continue whichever keyword came last, so a step
 * can take several lines. A line with no keyword also continues the previous one, which is
 * what makes pasted prose survive instead of being silently dropped.
 */

const KEYWORDS = ["given", "when", "then", "and", "but"] as const;
type Section = "given" | "when" | "then";

type ParsedScenario = {
  preconditions: string;
  steps: { action: string; expected_result: string }[];
};

/** Splits "When the user pays" into its keyword and the rest. */
const splitKeyword = (line: string): { keyword: string | null; rest: string } => {
  const match = /^\s*(given|when|then|and|but)\b[:\s]*(.*)$/i.exec(line);
  if (!match) return { keyword: null, rest: line.trim() };
  return { keyword: match[1].toLowerCase(), rest: match[2].trim() };
};

export const parseScenario = (text: string): ParsedScenario => {
  const preconditions: string[] = [];
  const steps: { action: string[]; expected_result: string[] }[] = [];
  // Lines before any keyword are setup -- context is what people write first, and calling
  // it an action would invent a step nobody asked for.
  let section: Section = "given";

  for (const raw of text.split("\n")) {
    if (!raw.trim()) continue;
    const { keyword, rest } = splitKeyword(raw);
    const body = keyword ? rest : raw.trim();

    if (keyword === "given") section = "given";
    else if (keyword === "when") {
      section = "when";
      steps.push({ action: [], expected_result: [] });
    } else if (keyword === "then") {
      section = "then";
      // A Then with no When before it still describes an expectation, so it gets a step to
      // live in rather than being thrown away.
      if (!steps.length) steps.push({ action: [], expected_result: [] });
    }
    // "and", "but" and bare lines keep the current section.

    if (!body) continue;
    if (section === "given") preconditions.push(body);
    else if (section === "when") steps[steps.length - 1].action.push(body);
    else steps[steps.length - 1].expected_result.push(body);
  }

  return {
    preconditions: preconditions.join("\n"),
    steps: steps.map((step) => ({
      action: step.action.join("\n"),
      expected_result: step.expected_result.join("\n"),
    })),
  };
};

/**
 * The stored shape back into Gherkin, so an existing case can be edited as text.
 *
 * Round-trips anything `parseScenario` produced. Cases written before this editor existed
 * come back as Given/When/Then too, which is the point -- their `|` syntax is not preserved
 * because it was never worth preserving.
 */
export const formatScenario = (preconditions: string, steps: { action: string; expected_result: string }[]) => {
  const lines: string[] = [];
  const push = (keyword: string, value: string) => {
    const parts = value.split("\n").filter((part) => part.trim());
    if (!parts.length) return;
    lines.push(`${keyword} ${parts[0]}`);
    // Extra lines continue the same keyword, which is what And means in Gherkin.
    parts.slice(1).forEach((part) => lines.push(`And ${part}`));
  };

  push("Given", preconditions);
  for (const step of steps) {
    push("When", step.action);
    push("Then", step.expected_result);
  }
  return lines.join("\n");
};

export const SCENARIO_KEYWORDS = KEYWORDS;
