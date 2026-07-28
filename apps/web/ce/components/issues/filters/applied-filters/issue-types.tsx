/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "react-router";
import { CloseIcon } from "@plane/propel/icons";
import { WorkItemTypeBadge } from "@/components/work-item-extensions";
import { useWorkspaceWorkItemTypes } from "@/hooks/use-work-item-extensions";

type Props = {
  handleRemove: (val: string) => void;
  values: string[];
  editable: boolean | undefined;
};

export const AppliedIssueTypeFilters = observer(function AppliedIssueTypeFilters(props: Props) {
  const { handleRemove, values, editable } = props;
  const { workspaceSlug } = useParams();
  const { data: workItemTypes } = useWorkspaceWorkItemTypes(workspaceSlug?.toString());

  return values.map((typeId) => {
    const type = workItemTypes?.find((item) => item.id === typeId);
    return (
      <div key={typeId} className="flex items-center gap-1 rounded-sm bg-layer-1 p-1 text-11">
        <WorkItemTypeBadge type={type} name={typeId} className="bg-transparent p-0" />
        {editable && (
          <button
            type="button"
            className="grid place-items-center text-tertiary hover:text-secondary"
            onClick={() => handleRemove(typeId)}
          >
            <CloseIcon height={10} width={10} strokeWidth={2} />
          </button>
        )}
      </div>
    );
  });
});
