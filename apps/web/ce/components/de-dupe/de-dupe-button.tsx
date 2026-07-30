/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import { CopyCheck } from "lucide-react";

type TDeDupeButtonRoot = {
  workspaceSlug: string;
  isDuplicateModalOpen: boolean;
  handleOnClick: () => void;
  label: string;
};

/**
 * The "this may already exist" affordance shown while a work item is being written.
 *
 * A warning, not a block. The matcher is trigram similarity over titles, which is right often
 * enough to be worth showing and wrong often enough that refusing the create would be
 * intolerable.
 */
export function DeDupeButtonRoot({ isDuplicateModalOpen, handleOnClick, label }: TDeDupeButtonRoot) {
  return (
    <button
      type="button"
      onClick={handleOnClick}
      aria-expanded={isDuplicateModalOpen}
      className="flex h-7 items-center gap-1.5 rounded border border-warning-subtle bg-warning-subtle px-2 text-11 font-medium text-warning-primary"
    >
      <CopyCheck className="size-3.5" />
      {label}
    </button>
  );
}
