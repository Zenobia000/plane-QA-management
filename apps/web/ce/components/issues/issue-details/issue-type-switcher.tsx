/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "react-router";
// store hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
// plane web components
import { IssueIdentifier } from "@/plane-web/components/issues/issue-details/issue-identifier";
import { WorkItemTypeBadge } from "@/components/work-item-extensions";
import { useProjectWorkItemTypes } from "@/hooks/use-work-item-extensions";

export type TIssueTypeSwitcherProps = {
  issueId: string;
  disabled: boolean;
};

export const IssueTypeSwitcher = observer(function IssueTypeSwitcher(props: TIssueTypeSwitcherProps) {
  const { issueId, disabled } = props;
  const { workspaceSlug } = useParams();
  // store hooks
  const {
    issue: { getIssueById, updateIssue },
  } = useIssueDetail();
  // derived values
  const issue = getIssueById(issueId);
  const slug = workspaceSlug?.toString();
  const { data: projectTypes } = useProjectWorkItemTypes(slug, issue?.project_id ?? undefined);
  const selectedType = projectTypes?.find((item) => item.type.id === issue?.type_id)?.type;

  if (!issue || !issue.project_id) return <></>;

  return (
    <div className="flex min-w-0 items-center gap-2">
      <IssueIdentifier issueId={issueId} projectId={issue.project_id} size="md" enableClickToCopyIdentifier />
      <label className="flex min-w-0 items-center rounded border border-subtle bg-surface-1 px-1.5 py-0.5">
        <WorkItemTypeBadge type={selectedType} compact className="mr-1 bg-transparent px-0" />
        <select
          aria-label="Work item type"
          className="max-w-36 bg-transparent text-12 text-secondary outline-none"
          value={issue.type_id ?? ""}
          disabled={disabled || !projectTypes?.length}
          onChange={(event) => {
            if (!slug) return;
            void updateIssue(slug, issue.project_id!, issueId, { type_id: event.target.value || null });
          }}
        >
          {!issue.type_id && <option value="">No type</option>}
          {projectTypes?.map((item) => (
            <option key={item.id} value={item.type.id}>
              {item.type.name}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
});
