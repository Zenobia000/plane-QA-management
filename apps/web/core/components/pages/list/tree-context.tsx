/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { createContext, useCallback, useContext, useMemo } from "react";
import { useParams } from "next/navigation";
// plane imports
import { useLocalStorage } from "@plane/hooks";

type TPagesTreeContext = {
  isExpanded: (pageId: string) => boolean;
  toggleExpanded: (pageId: string) => void;
  expand: (pageId: string) => void;
};

const PagesTreeContext = createContext<TPagesTreeContext | undefined>(undefined);

// A stable identity, so useLocalStorage's rehydrate effect does not resubscribe every render.
const NO_EXPANDED_PAGES: string[] = [];

type Props = {
  children: React.ReactNode;
};

/**
 * Remembers which pages are open, per project, across reloads.
 *
 * Kept in local storage rather than the page store because it describes this browser's view of
 * the tree, not the tree itself -- two people looking at the same project expand different parts
 * of it.
 */
export function PagesTreeProvider(props: Props) {
  const { children } = props;
  // params
  const { projectId } = useParams();
  // local storage
  const { storedValue, setValue } = useLocalStorage<string[]>(
    `pages-expanded-${projectId?.toString() ?? "unknown"}`,
    NO_EXPANDED_PAGES
  );

  const expandedIds = useMemo(() => storedValue ?? NO_EXPANDED_PAGES, [storedValue]);

  const isExpanded = useCallback((pageId: string) => expandedIds.includes(pageId), [expandedIds]);

  const toggleExpanded = useCallback(
    (pageId: string) => {
      setValue(expandedIds.includes(pageId) ? expandedIds.filter((id) => id !== pageId) : [...expandedIds, pageId]);
    },
    [expandedIds, setValue]
  );

  const expand = useCallback(
    (pageId: string) => {
      if (expandedIds.includes(pageId)) return;
      setValue([...expandedIds, pageId]);
    },
    [expandedIds, setValue]
  );

  const value = useMemo(() => ({ isExpanded, toggleExpanded, expand }), [isExpanded, toggleExpanded, expand]);

  return <PagesTreeContext.Provider value={value}>{children}</PagesTreeContext.Provider>;
}

export const usePagesTree = () => {
  const context = useContext(PagesTreeContext);
  if (!context) throw new Error("usePagesTree must be used within a PagesTreeProvider");
  return context;
};
