/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef, useState } from "react";
import { dropTargetForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { observer } from "mobx-react";
// plane imports
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TPageNavigationTabs } from "@plane/types";
import { cn } from "@plane/utils";
// components
import { ListLayout } from "@/components/core/list";
// plane web hooks
import type { EPageStoreType } from "@/hooks/store";
import { usePageStore } from "@/hooks/store";
// local imports
import { PageListBlock } from "./block";
import { PAGE_DRAG_TYPE, PageTreeBlock } from "./tree-block";
import { PagesTreeProvider } from "./tree-context";

type TPagesListRoot = {
  pageType: TPageNavigationTabs;
  storeType: EPageStoreType;
};

export const PagesListRoot = observer(function PagesListRoot(props: TPagesListRoot) {
  const { pageType, storeType } = props;
  // refs
  const containerRef = useRef<HTMLDivElement>(null);
  // states
  const [isDropTarget, setIsDropTarget] = useState(false);
  // store hooks
  const { getCurrentProjectFilteredPageIdsByTab, getPageTreeByTab, isSearchActive, movePageToParent } =
    usePageStore(storeType);
  // derived values
  const filteredPageIds = getCurrentProjectFilteredPageIdsByTab(pageType);
  const { rootIds } = getPageTreeByTab(pageType);

  // Dropping on the container rather than on a row files a page back at the top level. Row
  // targets sit inside this one and take precedence, so this only fires on the space between
  // them.
  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;

    return dropTargetForElements({
      element,
      getData: () => ({ type: PAGE_DRAG_TYPE, pageId: null }),
      canDrop: ({ source }) => source.data?.type === PAGE_DRAG_TYPE,
      onDragEnter: () => setIsDropTarget(true),
      onDragLeave: () => setIsDropTarget(false),
      onDrop: ({ source, location }) => {
        setIsDropTarget(false);
        // A row under the pointer has already handled it.
        if (location.current.dropTargets[0]?.element !== element) return;
        const draggedId = source.data?.pageId;
        if (typeof draggedId !== "string") return;
        movePageToParent(draggedId, null).catch((error) =>
          setToast({
            type: TOAST_TYPE.ERROR,
            title: "Error!",
            message: error?.error ?? error?.message ?? "The page could not be moved. Please try again.",
          })
        );
      },
    });
  }, [movePageToParent]);

  // While searching, results are shown flat: a match reads better on its own line than buried
  // under ancestors that did not match.
  if (isSearchActive) {
    if (!filteredPageIds) return <></>;
    return (
      <ListLayout>
        {filteredPageIds.map((pageId) => (
          <PageListBlock key={pageId} pageId={pageId} storeType={storeType} />
        ))}
      </ListLayout>
    );
  }

  return (
    <PagesTreeProvider>
      <div ref={containerRef} className={cn("h-full w-full", { "bg-layer-transparent-hover": isDropTarget })}>
        <ListLayout>
          {rootIds.map((pageId) => (
            <PageTreeBlock key={pageId} pageId={pageId} pageType={pageType} storeType={storeType} depth={0} />
          ))}
        </ListLayout>
      </div>
    </PagesTreeProvider>
  );
});
