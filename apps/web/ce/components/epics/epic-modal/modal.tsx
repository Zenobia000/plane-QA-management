/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import { observer } from "mobx-react";
import { useParams } from "react-router";
import type { TIssue } from "@plane/types";
import { CreateUpdateIssueModal } from "@/components/issues/issue-modal/modal";
import { useProjectWorkItemTypes } from "@/hooks/use-work-item-extensions";

export interface EpicModalProps {
  data?: Partial<TIssue>;
  isOpen: boolean;
  onClose: () => void;
  beforeFormSubmit?: () => Promise<void>;
  onSubmit?: (res: TIssue) => Promise<void>;
  fetchIssueDetails?: boolean;
  primaryButtonText?: {
    default: string;
    loading: string;
  };
  isProjectSelectionDisabled?: boolean;
}

/**
 * The work item modal with the type preloaded to the project's epic.
 *
 * An epic is an ordinary work item whose type carries `is_epic`, so it needs the same
 * form -- same fields, same validation, same submit path. A parallel modal would be a
 * second copy of all of that, and the copies would drift the first time either the form
 * or the create payload changed.
 *
 * Preloaded rather than locked: switching the type is the conversion `IssueTypeSwitcher`
 * also offers, and the server refuses the conversions that would invert the hierarchy, so
 * there is nothing left for this component to forbid.
 */
export const CreateUpdateEpicModal = observer(function CreateUpdateEpicModal(props: EpicModalProps) {
  const { data, ...rest } = props;
  const { workspaceSlug, projectId: routeProjectId } = useParams();
  const projectId = data?.project_id ?? routeProjectId?.toString();
  const { data: projectTypes } = useProjectWorkItemTypes(workspaceSlug?.toString(), projectId ?? undefined);

  const epicTypeId = projectTypes?.find((item) => item.type.is_epic)?.type.id;

  return (
    <CreateUpdateIssueModal
      {...rest}
      // An epic being edited already carries a type; only a new one needs the default.
      data={{ ...data, type_id: data?.type_id ?? epicTypeId ?? null }}
      modalTitle={data?.id ? "Update epic" : "Create epic"}
    />
  );
});
