/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { TEntityUpdate, TUpdateStatus } from "@plane/types";
import { UpdatesPanel } from "./panel";

const post = (id: string, status: TUpdateStatus, createdAt: string) =>
  ({
    id,
    entity_name: "project",
    entity_identifier: "p1",
    status,
    description: `body-${id}`,
    parent: null,
    reply_count: 0,
    label_ids: [],
    is_edited: false,
    actor_detail: null,
    created_at: createdAt,
  }) satisfies TEntityUpdate;

const board = (count: number) =>
  Array.from({ length: count }, (_, index) =>
    post(`p${index}`, "on_track", `2026-08-${String(index + 1).padStart(2, "0")}T00:00:00Z`)
  );

/** Read-only render: the composer is off, so this is purely about how the board reads. */
const render = (updates: TEntityUpdate[], props: Partial<Parameters<typeof UpdatesPanel>[0]> = {}) =>
  renderToStaticMarkup(<UpdatesPanel entityName="project" updates={updates} disabled onPost={vi.fn()} {...props} />);

describe("UpdatesPanel", () => {
  it("shows only the first few posts and offers the rest", () => {
    // The complaint this answers: a board that renders everything it holds is a running
    // log, and the reader has to scroll past it to reach anything else on the page.
    const markup = render(board(5));

    expect(markup).toContain("body-p4");
    expect(markup).toContain("body-p3");
    expect(markup).toContain("body-p2");
    expect(markup).not.toContain("body-p1");
    expect(markup).not.toContain("body-p0");
    expect(markup).toContain("project_overview.updates.show_rest");
  });

  it("does not offer the rest when everything already fits", () => {
    const markup = render(board(2));

    expect(markup).not.toContain("project_overview.updates.show_rest");
  });

  it("puts the newest first without being asked", () => {
    const markup = render(board(3));

    // p2 is the most recent, so it must appear before p1 in document order.
    expect(markup.indexOf("body-p2")).toBeLessThan(markup.indexOf("body-p1"));
  });

  it("offers the view controls once there is more than one post", () => {
    const markup = render(board(2));

    expect(markup).toContain("project_overview.updates.sort_label");
    expect(markup).toContain("project_overview.updates.group_label");
  });

  it("leaves the controls off a board with nothing to reorder", () => {
    const markup = render(board(1));

    expect(markup).not.toContain("project_overview.updates.sort_label");
    expect(markup).not.toContain("project_overview.updates.group_label");
  });

  it("says the board is empty rather than rendering a bare frame", () => {
    const markup = render([]);

    expect(markup).toContain("project_overview.updates.empty");
    expect(markup).not.toContain("project_overview.updates.sort_label");
  });

  it("keeps the separate control for posts the server has not sent yet", () => {
    // Folded-but-loaded and not-yet-fetched are different problems and must not collapse
    // into one control: only the second costs a round trip.
    const markup = render(board(3), { total: 12, onLoadAll: vi.fn() });

    expect(markup).toContain("project_overview.updates.show_earlier");
  });
});
