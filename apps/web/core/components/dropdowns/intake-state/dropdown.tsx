/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef, useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// hooks
import { useProjectState } from "@/hooks/store/use-project-state";
// local imports
import type { TWorkItemStateDropdownBaseProps } from "./base";
import { WorkItemStateDropdownBase } from "./base";

type TWorkItemStateDropdownProps = Omit<
  TWorkItemStateDropdownBaseProps,
  "stateIds" | "getStateById" | "onDropdownOpen" | "isInitializing"
> & {
  stateIds?: string[];
};

export const IntakeStateDropdown = observer(function IntakeStateDropdown(props: TWorkItemStateDropdownProps) {
  const { disabled, projectId, stateIds: propsStateIds } = props;
  // router params
  const { workspaceSlug } = useParams();
  // states
  const [stateLoader, setStateLoader] = useState(false);
  // refs
  const requestedFor = useRef<string | undefined>(undefined);
  // store hooks
  const { fetchProjectIntakeState, getProjectIntakeStateIds, getIntakeStateById } = useProjectState();
  // derived values
  const stateIds = propsStateIds ?? getProjectIntakeStateIds(projectId);

  // fetch states if not provided
  const onDropdownOpen = async () => {
    if ((stateIds === undefined || stateIds.length === 0) && workspaceSlug && projectId) {
      setStateLoader(true);
      await fetchProjectIntakeState(workspaceSlug.toString(), projectId);
      setStateLoader(false);
    }
  };

  /**
   * A disabled dropdown never opens, so opening was the wrong moment to load from.
   *
   * The intake detail panel renders this read-only, which left it permanently showing the
   * "State" placeholder instead of the item's actual state -- a field that reads as unset
   * on every item that has one. Read-only is exactly the case that has to fetch up front.
   */
  useEffect(() => {
    if (!disabled || !workspaceSlug || !projectId) return;
    if (stateIds !== undefined || requestedFor.current === projectId) return;
    requestedFor.current = projectId;
    void fetchProjectIntakeState(workspaceSlug.toString(), projectId);
  }, [disabled, fetchProjectIntakeState, projectId, stateIds, workspaceSlug]);

  return (
    <WorkItemStateDropdownBase
      {...props}
      getStateById={getIntakeStateById}
      isInitializing={stateLoader}
      stateIds={stateIds ?? []}
      onDropdownOpen={onDropdownOpen}
    />
  );
});
