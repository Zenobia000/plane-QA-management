/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useState } from "react";
import { observer } from "mobx-react";
import { AlertTriangle } from "lucide-react";
import { useParams } from "react-router";
import { ProjectOverviewService } from "@plane/services";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TProjectActivityEvent, TProjectOverview, TUpdateStatus } from "@plane/types";
import { PageHead } from "@/components/core/page-title";
import { readError } from "./errors";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { ActivityPanel, LinksPanel, MilestonesPanel } from "./panels";
import { OverviewHeader } from "./header";
import { ProgressBar } from "./progress-bar";
import { PropertiesPanel } from "./properties-panel";
import { UpdatesPanel } from "@/components/updates";

const overviewService = new ProjectOverviewService();

/**
 * The project's landing page: how it is going, without opening the work-item list.
 *
 * The same question `epics/page.tsx` answers for a subtree, one scope up -- and answered
 * the same way, by computing over the work beneath rather than by trusting a field someone
 * set by hand. `progress` therefore comes from the server, which counts state groups over
 * live work items, rather than from anything stored on the project row.
 *
 * Everything except activity arrives in one request. The page renders as a unit and each
 * part of it is cheap, so splitting the call would only buy showing a third of a screen
 * sooner. Activity is separate because it paginates.
 */
export default observer(function ProjectOverviewPage() {
  const { workspaceSlug, projectId } = useParams();
  const slug = workspaceSlug?.toString();
  const id = projectId?.toString();

  const { getProjectById, updateProject } = useProject();
  const { allowPermissions } = useUserPermissions();
  const [overview, setOverview] = useState<TProjectOverview | null>(null);
  const [activities, setActivities] = useState<TProjectActivityEvent[]>([]);
  const [activityCursor, setActivityCursor] = useState<string | null>(null);
  const [loadingMoreActivity, setLoadingMoreActivity] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const project = id ? getProjectById(id) : undefined;
  const canEdit = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.PROJECT,
    slug,
    id
  );

  const load = useCallback(async () => {
    if (!slug || !id) return;
    try {
      const [data, activity] = await Promise.all([
        overviewService.getOverview(slug, id),
        overviewService.getActivity(slug, id),
      ]);
      setOverview(data);
      setActivities(activity.results ?? []);
      // Only the first page. Anything already loaded is discarded on purpose: a refetch
      // after a write has to agree with the server about where the feed now starts.
      setActivityCursor(activity.next_page_results ? activity.next_cursor : null);
    } catch {
      setError("Could not load the project overview.");
    }
  }, [slug, id]);

  const loadMoreActivity = useCallback(async () => {
    if (!slug || !id || !activityCursor) return;
    setLoadingMoreActivity(true);
    try {
      const activity = await overviewService.getActivity(slug, id, activityCursor);
      setActivities((current) => [...current, ...(activity.results ?? [])]);
      setActivityCursor(activity.next_page_results ? activity.next_cursor : null);
    } catch (failure) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Could not load more activity",
        message: readError(failure, "The next page could not be loaded."),
      });
    } finally {
      setLoadingMoreActivity(false);
    }
  }, [slug, id, activityCursor]);

  useEffect(() => {
    void load();
  }, [load]);

  const postUpdate = async (status: TUpdateStatus, description: string) => {
    if (!slug || !id) return;
    await overviewService.createUpdate(slug, id, {
      entity_name: "project",
      entity_identifier: id,
      status,
      description,
    });
    await load();
  };

  /** The whole thread, when the reader asks past the newest few the overview embeds. */
  const loadAllUpdates = async () => (slug && id ? overviewService.listUpdates(slug, id, "project", id) : []);

  const loadReplies = async (updateId: string) =>
    slug && id ? overviewService.listReplies(slug, id, updateId, "project", id) : [];

  const postReply = async (parentId: string, description: string) => {
    if (!slug || !id) return;
    await overviewService.createUpdate(slug, id, {
      entity_name: "project",
      entity_identifier: id,
      // A reply carries its parent's verdict: it is a remark on that update, not a new one.
      status: overview?.updates.find((update) => update.id === parentId)?.status ?? "on_track",
      description,
      parent: parentId,
    });
    await load();
  };

  const createMilestone = async (name: string, targetDate: string | null) => {
    if (!slug || !id) return;
    await overviewService.createMilestone(slug, id, { name, target_date: targetDate });
    await load();
  };

  const renameMilestone = async (milestoneId: string, name: string, targetDate: string | null) => {
    if (!slug || !id) return;
    await overviewService.updateMilestone(slug, id, milestoneId, { name, target_date: targetDate });
    await load();
  };

  const removeMilestone = async (milestoneId: string) => {
    if (!slug || !id) return;
    await overviewService.deleteMilestone(slug, id, milestoneId);
    await load();
  };

  const addLink = async (url: string, title: string) => {
    if (!slug || !id) return;
    await overviewService.createLink(slug, id, { url, title });
    await load();
  };

  const removeLink = async (linkId: string) => {
    if (!slug || !id) return;
    await overviewService.deleteLink(slug, id, linkId);
    await load();
  };

  if (!slug || !id) return null;

  return (
    <>
      <PageHead title={project ? `${project.name} — Overview` : "Overview"} />
      {/* ContentWrapper owns the scroll now that this route has a layout, so this only
          constrains width and spacing. Keeping `overflow-y-auto` here would nest a second
          scroll container inside it. */}
      <main className="mx-auto flex w-full max-w-6xl flex-col gap-4 p-6">
        {project && (
          <OverviewHeader
            project={project}
            disabled={!canEdit}
            onChange={async (changes) => {
              await updateProject(slug, id, changes);
            }}
          />
        )}

        <header className="mt-6">
          <h1 className="text-18 font-semibold text-primary">{project?.name ?? "Overview"}</h1>
          {project?.description && <p className="mt-1 text-12 text-tertiary">{project.description}</p>}
        </header>

        {error && (
          <div className="flex items-center gap-2 rounded border border-danger-subtle bg-danger-subtle px-3 py-2 text-13 text-danger-primary">
            <AlertTriangle className="size-4" />
            {error}
          </div>
        )}

        {!overview && !error && <p className="text-13 text-tertiary">Loading…</p>}

        {overview && (
          <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
            <div className="flex flex-col gap-4">
              <ProgressBar progress={overview.progress} />
              <UpdatesPanel
                entityName="project"
                updates={overview.updates}
                total={overview.updates_total}
                disabled={!canEdit}
                onPost={postUpdate}
                onLoadReplies={loadReplies}
                onReply={postReply}
                onLoadAll={loadAllUpdates}
              />
              <ActivityPanel
                activities={activities}
                hasMore={!!activityCursor}
                loadingMore={loadingMoreActivity}
                onLoadMore={() => void loadMoreActivity()}
              />
            </div>
            <div className="flex flex-col gap-4">
              {project && (
                <PropertiesPanel
                  project={project}
                  disabled={!canEdit}
                  onChange={async (changes) => {
                    await updateProject(slug, id, changes);
                  }}
                />
              )}
              <MilestonesPanel
                milestones={overview.milestones}
                disabled={!canEdit}
                onCreate={createMilestone}
                onRename={renameMilestone}
                onRemove={removeMilestone}
              />
              <LinksPanel links={overview.links} disabled={!canEdit} onAdd={addLink} onRemove={removeLink} />
            </div>
          </div>
        )}
      </main>
    </>
  );
});
