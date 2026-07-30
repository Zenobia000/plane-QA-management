/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { Globe2, Lock } from "lucide-react";
import { FilterHeader, FilterOption } from "@/components/issues/issue-layouts/filters";
import { EViewAccess } from "@plane/types";

type Props = {
  // The caller holds `view_type` as an `EViewAccess[]`, which is optional in its filter
  // object, so the stub's `string[] | null` was narrower than every call site.
  appliedFilters: EViewAccess[] | string[] | null | undefined;
  handleUpdate: (val: string) => void;
  searchQuery: string;
  accessFilters: { key: EViewAccess; value: string }[];
};

export function FilterByAccess({ appliedFilters, handleUpdate, searchQuery, accessFilters }: Props) {
  const [previewEnabled, setPreviewEnabled] = useState(true);
  const options = accessFilters.filter((item) => item.value.toLowerCase().includes(searchQuery.toLowerCase()));

  return (
    <>
      <FilterHeader
        title={`Access${appliedFilters?.length ? ` (${appliedFilters.length})` : ""}`}
        isPreviewEnabled={previewEnabled}
        handleIsPreviewEnabled={() => setPreviewEnabled((current) => !current)}
      />
      {previewEnabled && (
        <div>
          {options.map((item) => {
            const Icon = item.key === EViewAccess.PRIVATE ? Lock : Globe2;
            return (
              <FilterOption
                key={item.key}
                isChecked={Boolean((appliedFilters as (string | EViewAccess)[] | null)?.includes(item.key))}
                onClick={() => handleUpdate(String(item.key))}
                icon={<Icon className="size-3" />}
                title={item.value}
              />
            );
          })}
          {!options.length && <p className="text-11 text-placeholder italic">No matches found</p>}
        </div>
      )}
    </>
  );
}
