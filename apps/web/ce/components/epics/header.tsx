/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { EpicIcon } from "@plane/propel/icons";
import { Tooltip } from "@plane/propel/tooltip";
import { EIssuesStoreType } from "@plane/types";
import { Breadcrumbs, Header } from "@plane/ui";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { CountChip } from "@/components/common/count-chip";
import { HeaderFilters } from "@/components/issues/filters";
// hooks
import { useIssues } from "@/hooks/store/use-issues";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
import { useAppRouter } from "@/hooks/use-app-router";
import { usePlatformOS } from "@/hooks/use-platform-os";
// plane web imports
import { CommonProjectBreadcrumbs } from "@/plane-web/components/breadcrumbs/common";
import { CreateUpdateEpicModal } from "@/plane-web/components/epics/epic-modal";

export const EpicsHeader = observer(function EpicsHeader() {
  // router
  const router = useAppRouter();
  const { workspaceSlug, projectId } = useParams();
  // states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  // store hooks
  const {
    issues: { getGroupIssueCount },
  } = useIssues(EIssuesStoreType.EPIC);
  const { t } = useTranslation();
  const { currentProjectDetails, loader } = useProject();
  const { allowPermissions } = useUserPermissions();
  const { isMobile } = usePlatformOS();

  const epicsCount = getGroupIssueCount(undefined, undefined, false);
  // Guests can read epics but not file them, matching the work-item list.
  const canUserCreateEpic = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.PROJECT
  );

  return (
    <>
      <CreateUpdateEpicModal isOpen={isCreateModalOpen} onClose={() => setIsCreateModalOpen(false)} />
      <Header>
        <Header.LeftItem>
          <div className="flex items-center gap-2.5">
            <Breadcrumbs onBack={() => router.back()} isLoading={loader === "init-loader"} className="flex-grow-0">
              <CommonProjectBreadcrumbs workspaceSlug={workspaceSlug?.toString()} projectId={projectId?.toString()} />
              <Breadcrumbs.Item
                component={
                  <BreadcrumbLink
                    label={t("sidebar.epics")}
                    href={`/${workspaceSlug}/projects/${projectId}/epics/`}
                    icon={<EpicIcon className="h-4 w-4 text-tertiary" />}
                    isLast
                  />
                }
                isLast
              />
            </Breadcrumbs>
            {epicsCount && epicsCount > 0 ? (
              <Tooltip
                isMobile={isMobile}
                tooltipContent={`There are ${epicsCount} ${epicsCount > 1 ? "epics" : "epic"} in this project`}
                position="bottom"
              >
                <CountChip count={epicsCount} />
              </Tooltip>
            ) : null}
          </div>
        </Header.LeftItem>
        <Header.RightItem>
          <div className="hidden gap-2 md:flex">
            <HeaderFilters
              projectId={projectId}
              currentProjectDetails={currentProjectDetails}
              workspaceSlug={workspaceSlug}
              canUserCreateIssue={canUserCreateEpic}
              storeType={EIssuesStoreType.EPIC}
            />
          </div>
          {canUserCreateEpic && (
            <Button variant="primary" size="lg" onClick={() => setIsCreateModalOpen(true)}>
              Add epic
            </Button>
          )}
        </Header.RightItem>
      </Header>
    </>
  );
});
