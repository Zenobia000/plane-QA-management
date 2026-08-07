/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import type { IIssueLabel, TEntityUpdate, TUpdateStatus } from "@plane/types";
import { UNTAGGED_SECTION, groupUpdates, overlap, sortUpdates } from "./shape";

const post = (id: string, status: TUpdateStatus, createdAt: string, labelIds: string[] = []) =>
  ({
    id,
    entity_name: "project",
    entity_identifier: "p1",
    status,
    description: id,
    parent: null,
    reply_count: 0,
    label_ids: labelIds,
    is_edited: false,
    actor_detail: null,
    created_at: createdAt,
  }) satisfies TEntityUpdate;

const topic = (id: string, name: string) => ({ id, name, color: "#fff" }) as IIssueLabel;

const AUDIT = topic("audit", "法規稽核");
const CROSS_TEAM = topic("cross", "跨團隊相依");
const LABELS = [AUDIT, CROSS_TEAM];

describe("sortUpdates", () => {
  const oldOffTrack = post("old-off", "off_track", "2026-08-01T00:00:00Z");
  const newOnTrack = post("new-on", "on_track", "2026-08-05T00:00:00Z");
  const midAtRisk = post("mid-risk", "at_risk", "2026-08-03T00:00:00Z");
  const board = [newOnTrack, midAtRisk, oldOffTrack];

  it("puts the newest first by default", () => {
    expect(sortUpdates(board, "newest").map((u) => u.id)).toEqual(["new-on", "mid-risk", "old-off"]);
  });

  it("reverses for oldest", () => {
    expect(sortUpdates(board, "oldest").map((u) => u.id)).toEqual(["old-off", "mid-risk", "new-on"]);
  });

  it("puts what is going wrong first, whatever its date", () => {
    // The whole reason this sort exists: the off-track post is the oldest on the board, so
    // newest-first buries the one thing a reader needed to see.
    expect(sortUpdates(board, "severity").map((u) => u.id)).toEqual(["old-off", "mid-risk", "new-on"]);
  });

  it("breaks a severity tie by recency rather than by input order", () => {
    const older = post("a", "at_risk", "2026-08-01T00:00:00Z");
    const newer = post("b", "at_risk", "2026-08-09T00:00:00Z");

    expect(sortUpdates([older, newer], "severity").map((u) => u.id)).toEqual(["b", "a"]);
    expect(sortUpdates([newer, older], "severity").map((u) => u.id)).toEqual(["b", "a"]);
  });

  it("does not mutate the caller's list", () => {
    const original = [newOnTrack, oldOffTrack];
    sortUpdates(original, "severity");

    expect(original.map((u) => u.id)).toEqual(["new-on", "old-off"]);
  });
});

describe("groupUpdates", () => {
  it("returns one section when grouping is off", () => {
    const board = [post("a", "on_track", "2026-08-01T00:00:00Z")];

    expect(groupUpdates(board, "none", LABELS)).toEqual([{ key: "all", updates: board }]);
  });

  it("returns nothing at all for an empty board, so no heading renders", () => {
    expect(groupUpdates([], "none", LABELS)).toEqual([]);
    expect(groupUpdates([], "status", LABELS)).toEqual([]);
    expect(groupUpdates([], "topic", LABELS)).toEqual([]);
  });

  it("orders status sections worst first, not alphabetically", () => {
    const board = [
      post("ok", "on_track", "2026-08-01T00:00:00Z"),
      post("bad", "off_track", "2026-08-02T00:00:00Z"),
      post("risky", "at_risk", "2026-08-03T00:00:00Z"),
    ];

    expect(groupUpdates(board, "status", LABELS).map((s) => s.key)).toEqual(["off_track", "at_risk", "on_track"]);
  });

  it("drops a status nobody has posted under", () => {
    const board = [post("ok", "on_track", "2026-08-01T00:00:00Z")];

    expect(groupUpdates(board, "status", LABELS).map((s) => s.key)).toEqual(["on_track"]);
  });

  it("preserves the incoming order inside a section", () => {
    // Grouping must not re-sort: sortUpdates already decided, and a second ordering here
    // would make the sort control lie about what it did.
    const board = sortUpdates(
      [post("early", "at_risk", "2026-08-01T00:00:00Z"), post("late", "at_risk", "2026-08-09T00:00:00Z")],
      "oldest"
    );

    expect(groupUpdates(board, "status", LABELS)[0].updates.map((u) => u.id)).toEqual(["early", "late"]);
  });

  it("follows the project's label order for topic sections", () => {
    const board = [
      post("c", "on_track", "2026-08-01T00:00:00Z", [CROSS_TEAM.id]),
      post("a", "on_track", "2026-08-02T00:00:00Z", [AUDIT.id]),
    ];

    expect(groupUpdates(board, "topic", LABELS).map((s) => s.label?.id)).toEqual([AUDIT.id, CROSS_TEAM.id]);
  });

  it("files a post under every topic it carries", () => {
    const board = [post("both", "at_risk", "2026-08-01T00:00:00Z", [AUDIT.id, CROSS_TEAM.id])];
    const sections = groupUpdates(board, "topic", LABELS);

    expect(sections.map((s) => s.key)).toEqual([AUDIT.id, CROSS_TEAM.id]);
    expect(sections.every((s) => s.updates[0].id === "both")).toBe(true);
  });

  it("keeps untagged posts, last", () => {
    const board = [
      post("filed", "on_track", "2026-08-02T00:00:00Z", [AUDIT.id]),
      post("loose", "on_track", "2026-08-01T00:00:00Z"),
    ];

    expect(groupUpdates(board, "topic", LABELS).map((s) => s.key)).toEqual([AUDIT.id, UNTAGGED_SECTION]);
  });

  it("treats a post whose only topic was deleted as untagged rather than losing it", () => {
    // A label removed from project settings leaves its id on the post. Filtering by known
    // labels alone would drop the announcement off the board entirely.
    const board = [post("orphan", "off_track", "2026-08-01T00:00:00Z", ["retired-label"])];

    expect(groupUpdates(board, "topic", LABELS).map((s) => s.key)).toEqual([UNTAGGED_SECTION]);
  });
});

describe("overlap", () => {
  it("is zero when every post sits in exactly one section", () => {
    const board = [post("a", "on_track", "2026-08-01T00:00:00Z", [AUDIT.id])];

    expect(overlap(groupUpdates(board, "topic", LABELS), board)).toBe(0);
  });

  it("counts the extra rows a two-topic post produces", () => {
    const board = [
      post("both", "at_risk", "2026-08-01T00:00:00Z", [AUDIT.id, CROSS_TEAM.id]),
      post("one", "on_track", "2026-08-02T00:00:00Z", [AUDIT.id]),
    ];

    // Three rows across two sections for two posts.
    expect(overlap(groupUpdates(board, "topic", LABELS), board)).toBe(1);
  });

  it("is zero for status grouping, which cannot double-count", () => {
    const board = [
      post("a", "at_risk", "2026-08-01T00:00:00Z", [AUDIT.id, CROSS_TEAM.id]),
      post("b", "on_track", "2026-08-02T00:00:00Z"),
    ];

    expect(overlap(groupUpdates(board, "status", LABELS), board)).toBe(0);
  });
});
