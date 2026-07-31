/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { LayoutDashboard } from "lucide-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Breadcrumbs, Header } from "@plane/ui";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
// hooks
import { useProject } from "@/hooks/store/use-project";
import { useAppRouter } from "@/hooks/use-app-router";
// plane web imports
import { CommonProjectBreadcrumbs } from "@/plane-web/components/breadcrumbs/common";

/**
 * The breadcrumb bar every other project page has.
 *
 * Overview shipped as a bare route with no layout, so it rendered without the header its
 * siblings carry and without `ContentWrapper` -- which is why it read as a different part
 * of the product. The icon matches the sidebar entry that links here.
 */
export const OverviewAppHeader = observer(function OverviewAppHeader() {
  const router = useAppRouter();
  const { workspaceSlug, projectId } = useParams();
  const { currentProjectDetails, loader } = useProject();
  const { t } = useTranslation();

  return (
    <Header>
      <Header.LeftItem>
        <Breadcrumbs onBack={router.back} isLoading={loader === "init-loader"}>
          <CommonProjectBreadcrumbs workspaceSlug={workspaceSlug?.toString()} projectId={projectId?.toString()} />
          <Breadcrumbs.Item
            component={
              <BreadcrumbLink
                label={t("sidebar.overview")}
                href={`/${workspaceSlug}/projects/${currentProjectDetails?.id}/overview`}
                icon={<LayoutDashboard className="h-4 w-4 text-tertiary" />}
                isLast
              />
            }
            isLast
          />
        </Breadcrumbs>
      </Header.LeftItem>
    </Header>
  );
});
