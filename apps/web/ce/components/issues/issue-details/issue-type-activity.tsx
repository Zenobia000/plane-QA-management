/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { ListTodo } from "lucide-react";
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import {
  IssueActivityBlockComponent,
  IssueLink,
} from "@/components/issues/issue-detail/issue-activity/activity/actions";

export type TIssueTypeActivity = { activityId: string; showIssue?: boolean; ends: "top" | "bottom" | undefined };

export const IssueTypeActivity = observer(function IssueTypeActivity(props: TIssueTypeActivity) {
  const { activityId, showIssue = true, ends } = props;
  const {
    activity: { getActivityById },
  } = useIssueDetail();
  const activity = getActivityById(activityId);
  if (!activity) return <></>;

  return (
    <IssueActivityBlockComponent
      icon={<ListTodo className="size-4 text-secondary" />}
      activityId={activityId}
      ends={ends}
    >
      changed the work item type
      {activity.old_value ? (
        <>
          {" "}
          from <span className="font-medium text-primary">{activity.old_value}</span>
        </>
      ) : null}{" "}
      to <span className="font-medium text-primary">{activity.new_value || "None"}</span>
      {showIssue ? " for " : ""}
      {showIssue && <IssueLink activityId={activityId} />}.
    </IssueActivityBlockComponent>
  );
});
