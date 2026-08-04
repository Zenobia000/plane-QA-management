/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { MutableRefObject } from "react";
import { useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import type { IGroupByColumn, IIssueDisplayProperties, TIssue } from "@plane/types";
// components
import { SpreadsheetIssueRowLoader } from "@/components/ui/loader/layouts/spreadsheet-layout-loader";
// hooks
import { useIntersectionObserver } from "@/hooks/use-intersection-observer";
import { useIssuesStore } from "@/hooks/use-issue-layout-store";
import type { TSelectionHelper } from "@/hooks/use-multiple-select";
// local imports
import type { TRenderQuickActions } from "../list/list-view-types";
import { SpreadsheetIssueRow } from "./issue-row";

type Props = {
  group: IGroupByColumn;
  groupIssueIds: string[] | undefined;
  showEmptyGroups: boolean;
  columnCount: number;
  displayProperties: IIssueDisplayProperties;
  isEstimateEnabled: boolean;
  quickActions: TRenderQuickActions;
  updateIssue: ((projectId: string | null, issueId: string, data: Partial<TIssue>) => Promise<void>) | undefined;
  canEditProperties: (projectId: string | undefined) => boolean;
  portalElement: MutableRefObject<HTMLDivElement | null>;
  containerRef: MutableRefObject<HTMLTableElement | null>;
  isScrolled: MutableRefObject<boolean>;
  spreadsheetColumnsList: (keyof IIssueDisplayProperties)[];
  selectionHelpers: TSelectionHelper;
  loadMoreIssues: (groupId?: string) => void;
  isEpic?: boolean;
};

/**
 * One group of a grouped spreadsheet: a heading row, its work items, and its own next page.
 *
 * A `<tbody>` per group rather than a table per group. The column widths are the point of this
 * layout -- a reader compares a due date in one story against a due date in another -- and
 * separate tables size their columns independently, so the comparison would break exactly
 * where grouping was supposed to help it. One table, repeated bodies, and the header stays a
 * single sticky row at the top instead of being reprinted between every group.
 *
 * Pagination is per group because the server pages that way: a grouped request opens a window
 * per group and fills each to the page size, so "load more" has to name the group it means.
 */
export const SpreadsheetGroup = observer(function SpreadsheetGroup(props: Props) {
  const {
    group,
    groupIssueIds,
    showEmptyGroups,
    columnCount,
    displayProperties,
    isEstimateEnabled,
    quickActions,
    updateIssue,
    canEditProperties,
    portalElement,
    containerRef,
    isScrolled,
    spreadsheetColumnsList,
    selectionHelpers,
    loadMoreIssues,
    isEpic = false,
  } = props;

  const { t } = useTranslation();
  const [intersectionElement, setIntersectionElement] = useState<HTMLTableRowElement | null>(null);
  const {
    issues: { getGroupIssueCount, getPaginationData, getIssueLoader },
  } = useIssuesStore();

  const groupIssueCount = getGroupIssueCount(group.id, undefined, false) ?? 0;
  const nextPageResults = getPaginationData(group.id, undefined)?.nextPageResults;
  const isPaginating = !!getIssueLoader(group.id);

  useIntersectionObserver(containerRef, isPaginating ? null : intersectionElement, loadMoreIssues, `100% 0% 100% 0%`);

  // Two ways to know more exists, because the first page does not report a cursor: before one
  // arrives, compare what is held against the group total the response already carried.
  const shouldLoadMore =
    nextPageResults === undefined && groupIssueIds ? groupIssueIds.length < groupIssueCount : !!nextPageResults;

  if (!showEmptyGroups && groupIssueCount <= 0) return null;

  return (
    <tbody>
      {/*
        Offsets by the header's own `h-11` so it parks directly beneath it, and sits above the
        rows' sticky first column (`z-10`) but below the header (`z-[12]`) -- otherwise the
        identifier column scrolls over the heading it belongs to.
      */}
      <tr className="sticky top-11 z-[11]">
        <td colSpan={columnCount} className="border-b border-subtle-1 bg-surface-2 px-4 py-2">
          <div className="flex items-center gap-2 text-13 font-medium text-primary">
            {group.icon}
            <span className="max-w-[40ch] truncate">{group.name}</span>
            <span className="text-secondary">{groupIssueCount}</span>
          </div>
        </td>
      </tr>
      {(groupIssueIds ?? []).map((id) => (
        <SpreadsheetIssueRow
          key={id}
          issueId={id}
          displayProperties={displayProperties}
          quickActions={quickActions}
          canEditProperties={canEditProperties}
          nestingLevel={0}
          isEstimateEnabled={isEstimateEnabled}
          updateIssue={updateIssue}
          portalElement={portalElement}
          containerRef={containerRef}
          isScrolled={isScrolled}
          spreadsheetColumnsList={spreadsheetColumnsList}
          selectionHelpers={selectionHelpers}
          isEpic={isEpic}
        />
      ))}
      {shouldLoadMore &&
        (isPaginating ? (
          <SpreadsheetIssueRowLoader columnCount={columnCount} />
        ) : (
          <tr ref={setIntersectionElement}>
            <td colSpan={columnCount} className="border-b border-subtle-1 bg-surface-1">
              <button
                type="button"
                className="flex h-11 w-full cursor-pointer items-center px-4 text-13 font-medium text-accent-primary hover:text-accent-secondary hover:underline"
                onClick={() => loadMoreIssues(group.id)}
              >
                {t("common.load_more")} &darr;
              </button>
            </td>
          </tr>
        ))}
    </tbody>
  );
});
