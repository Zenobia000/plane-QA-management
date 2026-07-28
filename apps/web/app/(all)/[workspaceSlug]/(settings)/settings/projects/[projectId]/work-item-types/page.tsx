/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { WorkItemExtensionSettings } from "@/components/work-item-extensions";
import type { Route } from "./+types/page";

export default function WorkItemTypesSettingsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  return (
    <SettingsContentWrapper
      header={
        <div className="flex h-full items-center px-5">
          <h1 className="text-14 font-medium text-primary">Work item types & properties</h1>
        </div>
      }
    >
      <PageHead title="Work item types & properties" />
      <WorkItemExtensionSettings workspaceSlug={workspaceSlug} projectId={projectId} />
    </SettingsContentWrapper>
  );
}
