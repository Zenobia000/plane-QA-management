# ADR 0007: A folder is declared, not inferred

- Status: accepted
- Date: 2026-08-04
- Owners: platform
- Related work items/test cases: `plane/tests/contract/app/test_page_folders.py`
- Supersedes/superseded by: supersedes the folder half of ADR 0006

## Context

ADR 0006 concluded that a folder is a page with children, and reused `Page.parent` rather than
adding a type. The tree machinery that decision protected is still right: the archive CTE, the
move walk and the delete re-homing are written against `parent`, they work, and nothing here
touches them.

What did not survive contact with a user is the _presentation_ that followed from it. Three
things were wrong at once, and they compound:

1. **A document changed type on its own.** The list drew a folder icon for anything with
   children, so filing a page under someone's document turned their document into a folder. Take
   the child away and it silently turned back.
2. **The icon lied about the click.** A folder icon promises a container; clicking it opened a
   text editor, because a folder was a page and pages open in the editor.
3. **The icon carried no information.** A disclosure chevron was already rendered beside it,
   meaning exactly the same thing — "has children" — so the folder glyph added nothing except
   a type distinction that did not exist.

The reported symptom was "資料夾自動變成資料夾這件事很奇怪" — which is precisely the first point,
arrived at from the outside.

## Decision drivers

- The nesting model is fine. The user asked for folders, not for a different tree.
- Whatever is drawn as a container must behave as one when clicked.
- Type is a decision someone makes, not a property of how many children a row happens to have.
- The rows that already exist have prose in them; a schema change must not delete it.

## Decision

Add `Page.is_folder`, chosen at creation.

- **Only a folder may take children.** Enforced on create and on re-parent. Without this the old
  behaviour returns by the back door — file under a document and it is a container again.
- **A folder has no document.** The description endpoint refuses writes; the client never opens
  an editor on one and the server does not rely on it remembering.
- **Clicking a folder expands it.** Only a document routes to the editor.
- **Conversion is allowed, but never lossily.** A page with prose cannot become a folder, because
  a folder never renders a body and the text would vanish from the product while sitting in the
  column. A folder holding pages cannot become a document.
- **Existing parents become folders** in the migration. That is what the list was already drawing,
  so nobody's tree changes shape; and it is required, since those rows hold children that only a
  folder is now allowed to hold.
- **A folder keeps `description_html`.** Nothing reads it while `is_folder` is true. Three rows on
  the authors' own instance had real prose, and dropping user text to satisfy a migration is the
  worse surprise — keeping it means converting back restores what was written.

## Consequences

- One additive migration, with a data pass. Reversible: the reverse unsets every flag.
- The tree traversals are untouched, so ADR 0006's actual argument still holds.
- Creating is now two acts — "Add page" and "Add folder" — instead of one act with an emergent
  second meaning.
- A folder row's link is empty, so ctrl/cmd-clicking one reopens the list rather than doing
  something useful. Accepted: the alternative is routing a container to a text editor, which is
  the bug this ADR exists to remove.
- Anything creating pages through the ORM rather than the API — the demo seed — has to set the
  flag itself. The API is the enforcement point, as elsewhere in this codebase.
