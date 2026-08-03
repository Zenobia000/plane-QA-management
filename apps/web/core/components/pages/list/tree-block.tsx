/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef, useState } from "react";
import { combine } from "@atlaskit/pragmatic-drag-and-drop/combine";
import { draggable, dropTargetForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { pointerOutsideOfPreview } from "@atlaskit/pragmatic-drag-and-drop/element/pointer-outside-of-preview";
import { setCustomNativeDragPreview } from "@atlaskit/pragmatic-drag-and-drop/element/set-custom-native-drag-preview";
import { observer } from "mobx-react";
import { useParams, useRouter } from "next/navigation";
import { createRoot } from "react-dom/client";
import { ChevronRight, Folder, FolderOpen, Plus } from "lucide-react";
// plane imports
import { Logo } from "@plane/propel/emoji-icon-picker";
import { PageIcon } from "@plane/propel/icons";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Tooltip } from "@plane/propel/tooltip";
import type { TPageNavigationTabs } from "@plane/types";
import { cn, getPageName } from "@plane/utils";
// components
import { ListItem } from "@/components/core/list";
import { BlockItemAction } from "@/components/pages/list/block-item-action";
// hooks
import { usePlatformOS } from "@/hooks/use-platform-os";
// plane web hooks
import type { EPageStoreType } from "@/hooks/store";
import { usePage, usePageStore } from "@/hooks/store";
// local imports
import { usePagesTree } from "./tree-context";

/** The drag payload every page row publishes, and every drop target reads. */
export const PAGE_DRAG_TYPE = "page-tree-item";

/** How far each level of the tree steps in, in pixels. */
const INDENT_PER_LEVEL = 18;

type Props = {
  pageId: string;
  pageType: TPageNavigationTabs;
  storeType: EPageStoreType;
  depth: number;
};

export const PageTreeBlock = observer(function PageTreeBlock(props: Props) {
  const { pageId, pageType, storeType, depth } = props;
  // refs
  const elementRef = useRef<HTMLDivElement>(null);
  // states
  const [isDragging, setIsDragging] = useState(false);
  const [isDropTarget, setIsDropTarget] = useState(false);
  const [isCreatingSubPage, setIsCreatingSubPage] = useState(false);
  // router
  const router = useRouter();
  const { workspaceSlug, projectId } = useParams();
  // store hooks
  const page = usePage({ pageId, storeType });
  const { getSubPageIds, getPageDescendantIds, movePageToParent, createPage } = usePageStore(storeType);
  const { isMobile } = usePlatformOS();
  // tree state
  const { isExpanded, toggleExpanded, expand } = usePagesTree();
  // derived values
  const subPageIds = getSubPageIds(pageType, pageId);
  const hasSubPages = subPageIds.length > 0;
  const expanded = isExpanded(pageId);
  const canBeFiled = !!page?.isContentEditable;
  const pageName = getPageName(page?.name);

  useEffect(() => {
    const element = elementRef.current;
    if (!element) return;

    return combine(
      draggable({
        element,
        canDrag: () => canBeFiled,
        getInitialData: () => ({ type: PAGE_DRAG_TYPE, pageId }),
        onDragStart: () => setIsDragging(true),
        onDrop: () => setIsDragging(false),
        onGenerateDragPreview: ({ nativeSetDragImage }) => {
          setCustomNativeDragPreview({
            getOffset: pointerOutsideOfPreview({ x: "8px", y: "8px" }),
            render: ({ container }) => {
              const root = createRoot(container);
              root.render(
                <div className="shadow-sm flex items-center gap-2 rounded-sm bg-surface-1 px-2 py-1 text-13">
                  <PageIcon className="size-4 flex-shrink-0 text-tertiary" />
                  <span className="truncate font-medium text-secondary">{pageName}</span>
                </div>
              );
              return () => root.unmount();
            },
            nativeSetDragImage,
          });
        },
      }),
      dropTargetForElements({
        element,
        getData: () => ({ type: PAGE_DRAG_TYPE, pageId }),
        canDrop: ({ source }) => {
          const draggedId = source.data?.pageId;
          if (source.data?.type !== PAGE_DRAG_TYPE || typeof draggedId !== "string") return false;
          // Nothing may be filed inside itself or inside its own sub-tree -- that would close
          // the tree into a ring, which the API refuses too.
          if (draggedId === pageId) return false;
          return !getPageDescendantIds(draggedId).includes(pageId);
        },
        onDragEnter: () => setIsDropTarget(true),
        onDragLeave: () => setIsDropTarget(false),
        onDrop: ({ source }) => {
          setIsDropTarget(false);
          const draggedId = source.data?.pageId;
          if (typeof draggedId !== "string") return;
          movePageToParent(draggedId, pageId)
            .then(() => expand(pageId))
            .catch((error) =>
              setToast({
                type: TOAST_TYPE.ERROR,
                title: "Error!",
                message: error?.error ?? error?.message ?? "The page could not be moved. Please try again.",
              })
            );
        },
      })
    );
  }, [canBeFiled, expand, getPageDescendantIds, movePageToParent, pageId, pageName]);

  const handleCreateSubPage = async () => {
    if (isCreatingSubPage) return;
    setIsCreatingSubPage(true);
    try {
      const subPage = await createPage({ access: page?.access, parent: pageId });
      expand(pageId);
      if (subPage?.id) router.push(`/${workspaceSlug}/projects/${projectId}/pages/${subPage.id}`);
    } catch (error: any) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Error!",
        message: error?.error ?? "The sub-page could not be created. Please try again.",
      });
    } finally {
      setIsCreatingSubPage(false);
    }
  };

  if (!page) return null;

  const { logo_props, getRedirectionLink } = page;

  return (
    <>
      <ListItem
        title={pageName}
        itemLink={getRedirectionLink()}
        isMobile={isMobile}
        parentRef={elementRef}
        className={cn({
          "ring-accent-primary bg-layer-transparent-hover ring-1 ring-inset": isDropTarget,
          "opacity-50": isDragging,
        })}
        leadingElement={
          <span className="flex flex-shrink-0 items-center" style={{ paddingLeft: depth * INDENT_PER_LEVEL }}>
            <button
              type="button"
              onClick={() => toggleExpanded(pageId)}
              className={cn(
                "grid size-5 place-items-center rounded-sm text-tertiary hover:bg-layer-transparent-hover",
                { invisible: !hasSubPages }
              )}
              aria-label={expanded ? `Collapse ${pageName}` : `Expand ${pageName}`}
              aria-expanded={hasSubPages ? expanded : undefined}
              tabIndex={hasSubPages ? 0 : -1}
            >
              <ChevronRight className={cn("size-4 transition-transform", { "rotate-90": expanded })} />
            </button>
          </span>
        }
        prependTitleElement={
          logo_props?.in_use ? (
            <Logo logo={logo_props} size={16} type="lucide" />
          ) : hasSubPages ? (
            expanded ? (
              <FolderOpen className="h-4 w-4 text-tertiary" />
            ) : (
              <Folder className="h-4 w-4 text-tertiary" />
            )
          ) : (
            <PageIcon className="h-4 w-4 text-tertiary" />
          )
        }
        appendTitleElement={
          hasSubPages ? (
            <span className="text-11 text-tertiary">
              {subPageIds.length} {subPageIds.length === 1 ? "page" : "pages"}
            </span>
          ) : undefined
        }
        quickActionElement={
          canBeFiled ? (
            <Tooltip tooltipContent="Add a sub-page" isMobile={isMobile}>
              <button
                type="button"
                onClick={handleCreateSubPage}
                disabled={isCreatingSubPage}
                aria-label={`Add a sub-page to ${pageName}`}
                className="grid size-5 flex-shrink-0 place-items-center rounded-sm text-tertiary opacity-0 outline-none group-hover:opacity-100 hover:bg-layer-transparent-hover focus-visible:opacity-100 disabled:cursor-not-allowed"
              >
                <Plus className="size-4" />
              </button>
            </Tooltip>
          ) : undefined
        }
        actionableItems={<BlockItemAction page={page} parentRef={elementRef} storeType={storeType} />}
      />
      {hasSubPages &&
        expanded &&
        subPageIds.map((subPageId) => (
          <PageTreeBlock
            key={subPageId}
            pageId={subPageId}
            pageType={pageType}
            storeType={storeType}
            depth={depth + 1}
          />
        ))}
    </>
  );
});
