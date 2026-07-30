/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { useParams } from "react-router";
import { Copy, Globe2 } from "lucide-react";
import { ProjectViewPublishService } from "@plane/services";
import type { IProjectView, TViewPublishSettings } from "@plane/types";
import { EModalPosition, EModalWidth, ModalCore } from "@plane/ui";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import { copyUrlToClipboard } from "@plane/utils";

const publishService = new ProjectViewPublishService();

type Props = {
  isOpen: boolean;
  view: IProjectView;
  onClose: () => void;
};

/**
 * Publish a saved view to a public anchor.
 *
 * `DeployBoard` already carried a `"view"` entity type, so this needed no schema -- only an
 * endpoint that names the entity, since `DeployBoardViewSet` hard-codes the project one.
 * Publishing also makes the view public: a private published view is a contradiction the
 * anchor resolves in favour of public anyway.
 */
export function PublishViewModal({ isOpen, view, onClose }: Props) {
  const { workspaceSlug, projectId } = useParams();
  const [settings, setSettings] = useState<TViewPublishSettings | null>(null);
  const [busy, setBusy] = useState(false);

  const slug = workspaceSlug?.toString();
  const id = projectId?.toString();

  useEffect(() => {
    if (!isOpen || !slug || !id) return;
    void publishService
      .getSettings(slug, id, view.id)
      .then((data) => setSettings(data?.anchor ? data : null))
      .catch(() => setSettings(null));
  }, [isOpen, slug, id, view.id]);

  const anchor = settings?.anchor;

  const publish = async () => {
    if (!slug || !id) return;
    setBusy(true);
    try {
      setSettings(await publishService.publish(slug, id, view.id, {}));
      setToast({ type: TOAST_TYPE.SUCCESS, title: "Published", message: "Anyone with the link can see this view." });
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: "Could not publish the view." });
    } finally {
      setBusy(false);
    }
  };

  const unpublish = async () => {
    if (!slug || !id) return;
    setBusy(true);
    try {
      await publishService.unpublish(slug, id, view.id);
      setSettings(null);
      setToast({ type: TOAST_TYPE.SUCCESS, title: "Unpublished", message: "The public link no longer works." });
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: "Could not unpublish the view." });
    } finally {
      setBusy(false);
    }
  };

  const publicUrl = anchor ? `${window.location.origin}/spaces/views/${anchor}` : "";

  return (
    <ModalCore isOpen={isOpen} handleClose={onClose} position={EModalPosition.CENTER} width={EModalWidth.XL}>
      <div className="space-y-4 p-5">
        <div className="flex items-center gap-2">
          <Globe2 className="size-4 text-tertiary" />
          <h3 className="text-16 font-medium text-primary">Publish {view.name}</h3>
        </div>

        {anchor ? (
          <>
            <div className="flex items-center gap-2 rounded border border-subtle bg-surface-2 px-2 py-1.5">
              <span className="min-w-0 flex-1 truncate text-12 text-secondary">{publicUrl}</span>
              <button
                type="button"
                aria-label="Copy public link"
                className="text-tertiary hover:text-primary"
                onClick={() =>
                  void copyUrlToClipboard(`spaces/views/${anchor}`).then(() =>
                    setToast({ type: TOAST_TYPE.SUCCESS, title: "Link copied", message: "" })
                  )
                }
              >
                <Copy className="size-3.5" />
              </button>
            </div>
            <p className="text-11 text-tertiary">
              Publishing made this view public. Unpublishing removes the link but leaves it public.
            </p>
          </>
        ) : (
          <p className="text-12 text-tertiary">
            Publishing creates a public link anyone can open, and makes this view visible to the whole project.
          </p>
        )}

        <div className="flex justify-end gap-2">
          <button type="button" className="h-8 rounded px-3 text-12 text-secondary" onClick={onClose}>
            Close
          </button>
          {anchor ? (
            <button
              type="button"
              className="bg-danger-solid h-8 rounded px-3 text-12 font-medium text-inverse disabled:opacity-50"
              disabled={busy}
              onClick={() => void unpublish()}
            >
              Unpublish
            </button>
          ) : (
            <button
              type="button"
              className="bg-accent-solid h-8 rounded px-3 text-12 font-medium text-inverse disabled:opacity-50"
              disabled={busy}
              onClick={() => void publish()}
            >
              Publish
            </button>
          )}
        </div>
      </div>
    </ModalCore>
  );
}
