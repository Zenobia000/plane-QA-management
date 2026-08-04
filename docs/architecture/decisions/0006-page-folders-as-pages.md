# ADR 0006: A folder is a page with children

- Status: accepted
- Date: 2026-08-03
- Owners: platform
- Related work items/test cases: `docs/planning/enterprise-parity-wbs.md` C.3; `plane/tests/contract/app/test_page_hierarchy.py`
- Supersedes/superseded by: folder-as-inference superseded by ADR 0007 (2026-08-04)

> **Partially superseded.** The tree argument here still holds and the cascades it protects are
> untouched: archive, move and delete are still written against `Page.parent`. What no longer
> holds is the answer to "what should a folder be" — inferring one from having children made a
> document change type when somebody nested under it, and made a folder icon open a text editor.
> Folders are now declared with `Page.is_folder`; see ADR 0007.

## Context

Pages could only be created one at a time into a flat list. There was no way to group a project's
test plans, regression checklists and defect reports under anything, and a QA project accumulates
enough of them that the list stops being readable within a sprint.

The schema was not the obstacle. `Page.parent` is a self-referencing foreign key that has been in
`plane/db/models/page.py` since the model was written, and the behaviour built on top of it was
already complete:

| Behaviour                                           | Where                                   |
| --------------------------------------------------- | --------------------------------------- |
| Archive/unarchive cascades down the sub-tree        | recursive CTE, `app/views/page/base.py` |
| Move between projects carries descendants along     | `PageViewSet.move`                      |
| Delete re-homes children rather than orphaning them | `PageViewSet.destroy`                   |
| `parent` accepted on write                          | `PageSerializer.Meta.fields`            |

What blocked it was one clause. `PageViewSet.get_queryset` ended in `.filter(parent__isnull=True)`,
so `list` returned only top-level pages and `retrieve` — which shares the queryset — returned 404
for anything nested. A sub-page could be created through the API and then reached by nothing. The
web app matched: `TPage` had no `parent` field at all, and no component read one.

So the question was not "what schema do folders need" but "what should a folder be, given a tree
already exists and works".

## Decision drivers

- The user asked for the Apple Files experience: nest, browse, drag to file.
- The cascades above are the expensive, correct part and they are already written against
  `Page.parent`. Anything that does not reuse them pays for them twice.
- A ring in the tree is unbounded: both the archive CTE and the move walk follow `parent` until they
  run out of rows, and a cycle means they never do. Nothing prevented one, because until now nothing
  could set `parent`.

## Considered options

### Option A — a folder is a page that has children

No schema change, no migration. Every page can hold sub-pages. The folder affordances — folder icon,
disclosure arrow, child count — are derived from whether the page has visible children.

Costs: there is no way to make an empty folder first and fill it afterwards; you make a page and add
sub-pages to it. A page is both a document and a container, which Finder does not allow.

Rebase impact: none. `Page.parent` is upstream's own field, used the way upstream's own cascades
already use it.

### Option B — an explicit folder entity

Add `Page.is_folder` (or a `PageFolder` model). Folders and documents become different things, which
is what Finder shows.

Costs: a migration, plus a "the parent must be a folder" rule that has to be enforced at create, at
update, at move and at drag-drop — four places that can disagree. The editor route grows a branch for
"this page cannot be opened". Upstream has no such field, so every rebase carries it.

## Decision

Option A. A folder is a page with children; there is no second kind of object.

Rules the implementation and tests enforce:

1. `parent` is exposed on read and accepted on write. `null` means top level.
2. A page may not be its own parent, and may not be filed inside its own sub-tree. Both are refused
   with 400 by the API and blocked client-side before the request is sent, because the cost of
   getting it wrong is a traversal that does not terminate.
3. A parent must be a page in the same project. A tree spanning two projects would leave `parent`
   crossing a boundary every other query assumes it does not — the same invariant `PageViewSet.move`
   already protects by carrying descendants along.
4. The list endpoint returns the project's pages flat, in one request; the tree is assembled by
   parent on the client. Depth costs no extra round trips.
5. A page whose parent is not visible in the current tab — a private page filed under a public one —
   is shown at the top level rather than dropped. Reachability is not conditional on which tab you
   are looking at.
6. Searching shows results flat. A match reads better on its own line than buried under ancestors
   that did not match.

## Consequences

### Positive

- Zero migration; the deployed schema already supports every case.
- The archive, move and delete cascades apply to user-made hierarchies unchanged, because they were
  always written against this field.
- Sub-pages became retrievable as a side effect: `retrieve` shares the queryset that was hiding them.

### Negative / accepted trade-offs

- No empty folders. The flow is "make a page, add sub-pages", not "make a folder, then fill it".
- A page in the middle of a tree carries both its own content and its children. That is Notion's
  model rather than Finder's, and it is strictly more permissive — a folder here can hold notes.
- Duplicating a page copies it as a sibling and does not copy its sub-tree. Existing behaviour, now
  visible where it was not before.

### Risks and mitigations

- **A cycle wedges the archive CTE** -> refused at the API with a descendant check, refused again in
  the store before the request, and pinned by
  `test_a_page_cannot_be_filed_inside_its_own_sub_tree`.
- **The list grows now that children are returned** -> the payload gains rows that were being hidden,
  not rows that did not exist. If a project ever outgrows one request, the fix is pagination of the
  same flat list, not re-hiding the children.

## Verification

- API contract tests: `plane/tests/contract/app/test_page_hierarchy.py` — 10 cases covering
  visibility, retrieval, filing, un-filing, self-parenting, sub-tree cycles, cross-project parents,
  creation under a parent, and archive cascade.
- Unit tests: `apps/web/core/store/pages/project-page.store.spec.ts` — 10 cases covering grouping,
  the cross-tab reachability rule, ancestor and descendant walks, the client-side cycle guard, and
  optimistic rollback.
- Migration/rollback verification: not applicable; no migration.

## Architecture diff

No new components. `PageViewSet.get_queryset` stops filtering to roots; `descendant_ids` is lifted to
module scope and shared by `move` and the re-parent guard. On the web side the pages list gains a
tree renderer and a drag-drop file-into path over the existing `ProjectPageStore`.
