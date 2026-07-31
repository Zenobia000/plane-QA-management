# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Telling a retirement apart from an edit.

A soft delete reaches a model through the same `save()` that an edit does, so a model that
refuses to be edited also refuses to be deleted -- and then outlives the parent that was
supposed to take it with it. That is not hypothetical: the testing entities forbid writes to
a published row, and 250 test case versions and 149 results were left alive under deleted
projects because the cascade could not save them.

The distinction is carried by `update_fields`. Everything that retires a row names exactly
the columns below; anything rewriting the row in full is an edit, whatever it intended.
Lives here rather than in `mixins` because the cascade task needs it too, and `mixins`
already imports that task.
"""

# The only columns a soft delete writes. `updated_at` is included because retiring a row is
# a modification of it -- leaving it out would silently stop soft deletes from touching the
# audit stamp they have always bumped.
SOFT_DELETE_FIELDS = ("deleted_at", "updated_at")


def is_soft_delete_save(kwargs) -> bool:
    """True when a `save()` is only stamping the soft-delete columns.

    Reads the `update_fields` the caller passed. A save naming no fields rewrites the whole
    row, so it counts as an edit; only one restricted to `SOFT_DELETE_FIELDS` is a
    lifecycle transition.
    """
    update_fields = kwargs.get("update_fields")
    if not update_fields:
        return False
    return set(update_fields) <= set(SOFT_DELETE_FIELDS)
