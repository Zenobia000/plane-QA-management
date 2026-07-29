/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ReactNode } from "react";
import type { TIssue } from "@plane/types";
import { ControlLink } from "@plane/ui";
import useIssuePeekOverviewRedirection from "@/hooks/use-issue-peek-overview-redirection";
import { usePlatformOS } from "@/hooks/use-platform-os";

type Props = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  sequenceId?: number;
  className?: string;
  children: ReactNode;
};

/**
 * Open a work item over Testing rather than navigating away from it.
 *
 * Testing used plain router links here, so following a linked requirement or a
 * defect unmounted the whole tab: the open case, the selected folder and the
 * scroll position were gone, and coming back re-ran the library fetch. The rest
 * of the product reaches work items through the peek overview instead, which is
 * also what Notion does for database relations — the row opens over what you
 * were reading, and closing it puts you back exactly where you were.
 *
 * ControlLink keeps a real anchor underneath, so ⌘/Ctrl-click, middle click and
 * "copy link address" behave as they should; only a plain click is intercepted.
 * useIssuePeekOverviewRedirection owns the peek-versus-navigate decision,
 * including falling back to a full page on mobile where a panel does not fit.
 *
 * The hook reads five fields off the work item and Testing's API returns two of
 * them, the project coming from the route. Passing that subset keeps the routing
 * decision in the hook rather than restating it here.
 */
export function WorkItemLink({ workspaceSlug, projectId, issueId, sequenceId, className, children }: Props) {
  const { handleRedirection } = useIssuePeekOverviewRedirection();

  const workItem = { id: issueId, project_id: projectId, sequence_id: sequenceId } as TIssue;

  // usePlatformOS reads window.navigator unguarded, and it is only named like a
  // hook — it holds no state. Asking at click time instead of render time keeps
  // this component renderable on the server, which is how its specs drive it.
  const open = () => handleRedirection(workspaceSlug, workItem, usePlatformOS().isMobile);

  return (
    <ControlLink
      href={`/${workspaceSlug}/projects/${projectId}/issues/${issueId}`}
      onClick={open}
      // ControlLink defaults to _blank. That only decides what an unintercepted
      // click does, since ⌘/Ctrl-click opens a tab whichever target is set — so
      // the default's only real effect is a stray tab before the handler runs.
      target="_self"
      className={className}
    >
      {children}
    </ControlLink>
  );
}
