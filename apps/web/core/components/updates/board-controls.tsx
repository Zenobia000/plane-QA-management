/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { ChevronDown, ChevronRight } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { BOARD_GROUPINGS, BOARD_SORTS, type TBoardGrouping, type TBoardSection, type TBoardSort } from "./shape";
import { UpdateStatusPill } from "./status-pill";

/**
 * The board's view controls and its section headings.
 *
 * Split out of `panel.tsx` because that file already carries the composer, the topic
 * filter and the thread, and none of this is coupled to any of them -- these two render
 * their arguments and nothing else.
 *
 * Native `<select>`s rather than the project's dropdown component. Both are short, closed
 * lists of view options with no search and no multi-select, which is the one case where the
 * platform control is smaller, keyboard-navigable for free, and correct on a phone.
 */

const SORT_KEYS: Record<TBoardSort, string> = {
  newest: "project_overview.updates.sort.newest",
  oldest: "project_overview.updates.sort.oldest",
  severity: "project_overview.updates.sort.severity",
};

const GROUP_KEYS: Record<TBoardGrouping, string> = {
  none: "project_overview.updates.group.none",
  status: "project_overview.updates.group.status",
  topic: "project_overview.updates.group.topic",
};

const SELECT_CLASS =
  "rounded border border-subtle bg-surface-1 px-1.5 py-0.5 text-10 font-medium text-secondary outline-none focus:border-accent-strong";

export function BoardControls({
  sort,
  grouping,
  onSort,
  onGrouping,
}: {
  sort: TBoardSort;
  grouping: TBoardGrouping;
  onSort: (next: TBoardSort) => void;
  onGrouping: (next: TBoardGrouping) => void;
}) {
  const { t } = useTranslation();

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
      <label className="flex items-center gap-1.5">
        <span className="text-10 text-tertiary">{t("project_overview.updates.sort_label")}</span>
        <select className={SELECT_CLASS} value={sort} onChange={(event) => onSort(event.target.value as TBoardSort)}>
          {BOARD_SORTS.map((value) => (
            <option key={value} value={value}>
              {t(SORT_KEYS[value])}
            </option>
          ))}
        </select>
      </label>
      <label className="flex items-center gap-1.5">
        <span className="text-10 text-tertiary">{t("project_overview.updates.group_label")}</span>
        <select
          className={SELECT_CLASS}
          value={grouping}
          onChange={(event) => onGrouping(event.target.value as TBoardGrouping)}
        >
          {BOARD_GROUPINGS.map((value) => (
            <option key={value} value={value}>
              {t(GROUP_KEYS[value])}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

/**
 * One section's heading: what it collects, how many, and whether it is open.
 *
 * The count is on the heading rather than left to be inferred from the rows, because a
 * folded section shows no rows at all -- and knowing that "off track" holds four is most of
 * the reason to look.
 */
export function SectionHeader({
  section,
  open,
  onToggle,
}: {
  section: TBoardSection;
  open: boolean;
  onToggle: () => void;
}) {
  const { t } = useTranslation();
  const color = section.label?.color || "#a3a3a3";

  return (
    <button
      type="button"
      aria-expanded={open}
      onClick={onToggle}
      className="flex w-full items-center gap-2 py-1 text-left"
    >
      {open ? (
        <ChevronDown className="size-3.5 shrink-0 text-tertiary" />
      ) : (
        <ChevronRight className="size-3.5 shrink-0 text-tertiary" />
      )}
      {section.status ? (
        <UpdateStatusPill status={section.status} />
      ) : (
        <span className="inline-flex min-w-0 items-center gap-1 text-11 font-medium text-primary">
          {section.label && <span className="size-1.5 shrink-0 rounded-full" style={{ backgroundColor: color }} />}
          <span className="truncate">{section.label?.name ?? t("project_overview.updates.untagged")}</span>
        </span>
      )}
      <span className="text-10 text-tertiary">{section.updates.length}</span>
    </button>
  );
}
