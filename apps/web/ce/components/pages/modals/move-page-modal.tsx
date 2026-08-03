/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "react-router";
import { EModalPosition, EModalWidth, ModalCore } from "@plane/ui";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import { ProjectPageService } from "@/services/page/project-page.service";
// hooks
import { useProject } from "@/hooks/store/use-project";
// store types
import type { TPageInstance } from "@/store/pages/base-page";

const pageService = new ProjectPageService();

export type TMovePageModalProps = {
  isOpen: boolean;
  onClose: () => void;
  page: TPageInstance;
};

/**
 * Move a page to another project in the same workspace.
 *
 * The move swaps the `ProjectPage` membership row rather than copying, so versions, labels
 * and the description stay attached to the same page. Descendants come along, because a
 * page tree split across two projects would leave `parent` crossing a boundary every other
 * query assumes it does not.
 */
export const MovePageModal = observer(function MovePageModal({ isOpen, onClose, page }: TMovePageModalProps) {
  const { workspaceSlug, projectId } = useParams();
  const { joinedProjectIds, getProjectById } = useProject();
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);

  const slug = workspaceSlug?.toString();
  const currentProjectId = projectId?.toString();
  const destinations = (joinedProjectIds ?? []).filter((id) => id !== currentProjectId);

  const move = async () => {
    if (!slug || !currentProjectId || !target || !page.id) return;
    setBusy(true);
    try {
      await pageService.move(slug, currentProjectId, page.id, target);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Moved",
        message: `Moved to ${getProjectById(target)?.name ?? "the other project"}.`,
      });
      onClose();
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: "Could not move the page." });
    } finally {
      setBusy(false);
    }
  };

  return (
    <ModalCore isOpen={isOpen} handleClose={onClose} position={EModalPosition.CENTER} width={EModalWidth.XL}>
      <div className="space-y-4 p-5">
        <h3 className="text-16 font-medium text-primary">Move {page.name || "page"}</h3>
        <p className="text-12 text-tertiary">
          Sub-pages move with it. Nothing is copied, so history and links are preserved.
        </p>

        <select
          aria-label="Destination project"
          className="h-9 w-full rounded border border-subtle bg-surface-1 px-2 text-12 text-primary outline-none focus:border-accent-strong"
          value={target}
          onChange={(event) => setTarget(event.target.value)}
        >
          <option value="">Choose a project</option>
          {destinations.map((id) => (
            <option key={id} value={id}>
              {getProjectById(id)?.name ?? id}
            </option>
          ))}
        </select>

        <div className="flex justify-end gap-2">
          <button type="button" className="h-8 rounded px-3 text-12 text-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="h-8 rounded bg-accent-primary px-3 text-12 font-medium text-inverse disabled:opacity-50"
            disabled={busy || !target}
            onClick={() => void move()}
          >
            Move
          </button>
        </div>
      </div>
    </ModalCore>
  );
});
