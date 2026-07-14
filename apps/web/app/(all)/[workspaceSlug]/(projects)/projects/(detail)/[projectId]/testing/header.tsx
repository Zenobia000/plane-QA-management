/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { FlaskConical } from "lucide-react";
import { useParams } from "next/navigation";
import { Breadcrumbs, Header } from "@plane/ui";
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { useAppRouter } from "@/hooks/use-app-router";
import { CommonProjectBreadcrumbs } from "@/plane-web/components/breadcrumbs/common";

export function TestingHeader() {
  const router = useAppRouter();
  const { workspaceSlug, projectId } = useParams();

  return (
    <Header>
      <Header.LeftItem>
        <Breadcrumbs onBack={router.back}>
          <CommonProjectBreadcrumbs workspaceSlug={workspaceSlug?.toString()} projectId={projectId?.toString()} />
          <Breadcrumbs.Item
            component={
              <BreadcrumbLink
                label="Testing"
                href={`/${workspaceSlug}/projects/${projectId}/testing/`}
                icon={<FlaskConical className="size-4 text-tertiary" />}
                isLast
              />
            }
            isLast
          />
        </Breadcrumbs>
      </Header.LeftItem>
    </Header>
  );
}
