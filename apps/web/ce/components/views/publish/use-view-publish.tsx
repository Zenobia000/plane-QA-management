/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { Globe2 } from "lucide-react";

/**
 * The publish entry in a view's context menu, plus the modal's open state.
 *
 * Returns `undefined` for the menu item when the caller may not publish, which is how the
 * quick-actions menu already expects to be told "this action does not apply here".
 */
export const useViewPublish = (isPublished: boolean, isAuthorized: boolean) => {
  const [isPublishModalOpen, setPublishModalOpen] = useState(false);

  return {
    isPublishModalOpen,
    setPublishModalOpen,
    publishContextMenu: isAuthorized
      ? {
          key: "publish",
          action: () => setPublishModalOpen(true),
          title: isPublished ? "Publish settings" : "Publish",
          icon: Globe2,
        }
      : undefined,
  };
};
