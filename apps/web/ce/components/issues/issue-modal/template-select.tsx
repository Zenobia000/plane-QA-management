/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { useParams } from "react-router";
import { EnterpriseService } from "@plane/services";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import type { TTemplate } from "@plane/types";

const service = new EnterpriseService();

export type TWorkItemTemplateDropdownSize = "xs" | "sm";

export type TWorkItemTemplateSelect = {
  projectId: string | null;
  typeId: string | null;
  disabled?: boolean;
  size?: TWorkItemTemplateDropdownSize;
  placeholder?: string;
  renderChevron?: boolean;
  dropDownContainerClassName?: string;
  handleModalClose: () => void;
  handleFormChange?: () => void;
};

/**
 * Create a work item from a saved template.
 *
 * Applying closes the modal rather than filling the form, because the endpoint creates the
 * item server-side -- it has to, since resolving the payload against the project's current
 * states is what lets a template survive the deletion of something it names. Any key that
 * could not be resolved is reported, so a silently thinner work item is not the first thing
 * anyone learns about a stale template.
 */
export function WorkItemTemplateSelect(props: TWorkItemTemplateSelect) {
  const { projectId, disabled = false, dropDownContainerClassName, handleModalClose } = props;
  const { workspaceSlug } = useParams();
  const [templates, setTemplates] = useState<TTemplate[]>([]);
  const [busy, setBusy] = useState(false);

  const slug = workspaceSlug?.toString();

  useEffect(() => {
    if (!slug) return;
    service
      .listTemplates(slug, "work_item")
      .then(setTemplates)
      .catch(() => setTemplates([]));
  }, [slug]);

  const apply = async (templateId: string) => {
    if (!slug || !projectId || !templateId) return;
    setBusy(true);
    try {
      const created = await service.applyTemplate(slug, projectId, templateId);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Created",
        message: created.dropped.length
          ? `Created ${created.name}. ${created.dropped.join(", ")} could not be applied.`
          : `Created ${created.name}.`,
      });
      handleModalClose();
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: "Could not apply the template." });
    } finally {
      setBusy(false);
    }
  };

  if (!templates.length) return <></>;

  return (
    <label
      className={`flex h-7 min-w-0 items-center rounded border border-subtle bg-surface-1 px-1.5 ${
        dropDownContainerClassName ?? ""
      }`}
    >
      <select
        aria-label="Work item template"
        className="min-w-0 flex-1 bg-transparent text-12 text-primary outline-none"
        value=""
        disabled={disabled || busy || !projectId}
        onChange={(event) => void apply(event.target.value)}
      >
        <option value="">Use a template…</option>
        {templates.map((template) => (
          <option key={template.id} value={template.id}>
            {template.name}
          </option>
        ))}
      </select>
    </label>
  );
}
