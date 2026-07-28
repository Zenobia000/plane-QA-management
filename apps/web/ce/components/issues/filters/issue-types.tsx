/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "react-router";
import { FilterHeader, FilterOption } from "@/components/issues/issue-layouts/filters";
import { WorkItemTypeBadge } from "@/components/work-item-extensions";
import { useProjectWorkItemTypes } from "@/hooks/use-work-item-extensions";

type Props = {
  appliedFilters: string[] | null;
  handleUpdate: (val: string) => void;
  searchQuery: string;
};

export const FilterIssueTypes = observer(function FilterIssueTypes(props: Props) {
  const { appliedFilters, handleUpdate, searchQuery } = props;
  const { workspaceSlug, projectId } = useParams();
  const { data: projectTypes } = useProjectWorkItemTypes(workspaceSlug?.toString(), projectId?.toString());
  const [previewEnabled, setPreviewEnabled] = useState(true);
  const options = useMemo(
    () =>
      (projectTypes ?? [])
        .filter((item) => item.type.name.toLowerCase().includes(searchQuery.toLowerCase()))
        .sort(
          (left, right) =>
            Number((appliedFilters ?? []).includes(right.type.id)) -
            Number((appliedFilters ?? []).includes(left.type.id))
        ),
    [appliedFilters, projectTypes, searchQuery]
  );

  return (
    <>
      <FilterHeader
        title={`Work item type${appliedFilters?.length ? ` (${appliedFilters.length})` : ""}`}
        isPreviewEnabled={previewEnabled}
        handleIsPreviewEnabled={() => setPreviewEnabled((current) => !current)}
      />
      {previewEnabled && (
        <div>
          {options.map((item) => (
            <FilterOption
              key={item.id}
              isChecked={Boolean(appliedFilters?.includes(item.type.id))}
              onClick={() => handleUpdate(item.type.id)}
              icon={<WorkItemTypeBadge type={item.type} compact className="bg-transparent p-0" />}
              title={item.type.name}
            />
          ))}
          {!options.length && <p className="text-11 text-placeholder italic">No matches found</p>}
        </div>
      )}
    </>
  );
});
