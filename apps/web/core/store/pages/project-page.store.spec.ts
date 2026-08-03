import { describe, expect, it, vi } from "vitest";
import type { TPage } from "@plane/types";
import type { RootStore } from "@/plane-web/store/root.store";
import { ProjectPageStore } from "./project-page.store";
import type { TProjectPage } from "./project-page";

const PROJECT_ID = "project-1";

const rootStoreMock = () =>
  ({
    router: { projectId: PROJECT_ID, workspaceSlug: "acme" },
    user: { permission: { getProjectRoleByWorkspaceSlugAndProjectId: vi.fn() } },
    favorite: { entityMap: {} },
  }) as unknown as RootStore;

type PageSeed = Partial<TPage> & { id: string };

/** A page as the store sees it: plain data plus the one method the move path calls. */
const seedPage = (seed: PageSeed) =>
  ({
    access: 0,
    archived_at: null,
    name: seed.id,
    parent: null,
    project_ids: [PROJECT_ID],
    updated_at: new Date("2026-01-01T00:00:00Z"),
    ...seed,
    mutateProperties(data: Partial<TPage>) {
      Object.assign(this, data);
    },
  }) as unknown as TProjectPage;

const storeWith = (...seeds: PageSeed[]) => {
  const store = new ProjectPageStore(rootStoreMock());
  for (const seed of seeds) store.data[seed.id] = seedPage(seed);
  return store;
};

describe("ProjectPageStore hierarchy", () => {
  it("groups pages under the parent they are filed against", () => {
    const store = storeWith(
      { id: "plan" },
      { id: "sprint-12", parent: "plan" },
      { id: "smoke", parent: "sprint-12" },
      { id: "weekly" }
    );

    const tree = store.getPageTreeByTab("public");

    expect(tree.rootIds.toSorted()).toEqual(["plan", "weekly"]);
    expect(tree.childIdsByParent["plan"]).toEqual(["sprint-12"]);
    expect(tree.childIdsByParent["sprint-12"]).toEqual(["smoke"]);
  });

  it("lists a page at the top level when its parent is not in the same tab", () => {
    // A private page filed under a public one: the parent is absent from the private tab, and
    // dropping the child would make it unreachable.
    const store = storeWith({ id: "plan", access: 0 }, { id: "secret", access: 1, parent: "plan" });

    const privateTab = store.getPageTreeByTab("private");

    expect(privateTab.rootIds).toEqual(["secret"]);
    expect(privateTab.childIdsByParent).toEqual({});
  });

  it("keeps an archived page out of the tree its unarchived parent is in", () => {
    const store = storeWith({ id: "plan" }, { id: "old", parent: "plan", archived_at: "2026-01-02" });

    expect(store.getPageTreeByTab("public").childIdsByParent["plan"]).toBeUndefined();
    expect(store.getPageTreeByTab("archived").rootIds).toEqual(["old"]);
  });

  it("walks ancestors from the top level down", () => {
    const store = storeWith({ id: "plan" }, { id: "sprint-12", parent: "plan" }, { id: "smoke", parent: "sprint-12" });

    expect(store.getPageAncestorIds("smoke")).toEqual(["plan", "sprint-12"]);
    expect(store.getPageAncestorIds("plan")).toEqual([]);
  });

  it("collects every descendant, at any depth", () => {
    const store = storeWith(
      { id: "plan" },
      { id: "sprint-12", parent: "plan" },
      { id: "smoke", parent: "sprint-12" },
      { id: "weekly" }
    );

    expect(store.getPageDescendantIds("plan").toSorted()).toEqual(["smoke", "sprint-12"]);
    expect(store.getPageDescendantIds("weekly")).toEqual([]);
  });

  it("refuses to file a page inside itself or its own sub-tree", async () => {
    const store = storeWith({ id: "plan" }, { id: "sprint-12", parent: "plan" }, { id: "smoke", parent: "sprint-12" });
    const update = vi.spyOn(store.service, "update");

    await expect(store.movePageToParent("plan", "plan")).rejects.toThrow(/its own parent/);
    await expect(store.movePageToParent("plan", "smoke")).rejects.toThrow(/its own sub-pages/);
    expect(update).not.toHaveBeenCalled();
  });

  it("puts the page back where it was when the server refuses the move", async () => {
    const store = storeWith({ id: "plan" }, { id: "weekly" });
    vi.spyOn(store.service, "update").mockRejectedValue({ error: "nope" });

    await expect(store.movePageToParent("weekly", "plan")).rejects.toEqual({ error: "nope" });
    expect(store.getPageById("weekly")?.parent).toBeNull();
  });

  it("files the page and tells the server once, on a move that sticks", async () => {
    const store = storeWith({ id: "plan" }, { id: "weekly" });
    const update = vi.spyOn(store.service, "update").mockResolvedValue({} as TPage);

    await store.movePageToParent("weekly", "plan");

    expect(store.getPageById("weekly")?.parent).toBe("plan");
    expect(update).toHaveBeenCalledWith("acme", PROJECT_ID, "weekly", { parent: "plan" });
  });

  it("does nothing when the page is already filed there", async () => {
    const store = storeWith({ id: "plan" }, { id: "weekly", parent: "plan" });
    const update = vi.spyOn(store.service, "update");

    await store.movePageToParent("weekly", "plan");

    expect(update).not.toHaveBeenCalled();
  });

  it("treats a search query as the switch out of tree mode", () => {
    const store = storeWith({ id: "plan" });

    expect(store.isSearchActive).toBe(false);
    store.updateFilters("searchQuery", "  ");
    expect(store.isSearchActive).toBe(false);
    store.updateFilters("searchQuery", "smoke");
    expect(store.isSearchActive).toBe(true);
  });
});
