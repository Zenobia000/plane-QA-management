/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { FolderInput } from "lucide-react";
import { Tooltip } from "@plane/propel/tooltip";
import { MovePageModal } from "@/plane-web/components/pages/modals/move-page-modal";
// store
import type { TPageInstance } from "@/store/pages/base-page";

export type TPageMoveControlProps = {
  page: TPageInstance;
};

export const PageMoveControl = observer(function PageMoveControl({ page }: TPageMoveControlProps) {
  const [isOpen, setIsOpen] = useState(false);

  // Moving a page is an edit to it, so it follows the same permission the editor does.
  if (!page.canCurrentUserEditPage) return null;

  return (
    <>
      <MovePageModal isOpen={isOpen} onClose={() => setIsOpen(false)} page={page} />
      <Tooltip tooltipContent="Move to another project">
        <button
          type="button"
          aria-label="Move page"
          className="grid size-6 place-items-center rounded text-tertiary hover:bg-surface-2 hover:text-primary"
          onClick={() => setIsOpen(true)}
        >
          <FolderInput className="size-4" />
        </button>
      </Tooltip>
    </>
  );
});
