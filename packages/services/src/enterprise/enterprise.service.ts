/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type {
  TAutomation,
  TDashboard,
  TDashboardWidget,
  TDashboardWidgetData,
  TDuplicateCandidate,
  TInitiative,
  TInitiativeProgress,
  TStateTransition,
  TStateTransitionPayload,
  TTeamspace,
  TTemplate,
  TTemplateKind,
  TWorklog,
  TWorklogSummary,
} from "@plane/types";
import { APIService } from "../api.service";

/**
 * One client for the features the commercial build gates.
 *
 * Grouped rather than split per family because they share a single audience -- the settings
 * and detail surfaces that fill the `ce/` stubs -- and eight one-method services would be
 * eight files to find instead of one.
 */
export class EnterpriseService extends APIService {
  constructor(BASE_URL?: string) {
    super(BASE_URL || API_BASE_URL);
  }

  private unwrap<T>(promise: Promise<{ data: T }>): Promise<T> {
    return promise
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  // Workflows -------------------------------------------------------------

  listTransitions(workspaceSlug: string, projectId: string): Promise<TStateTransition[]> {
    return this.unwrap(this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/state-transitions/`));
  }

  createTransition(
    workspaceSlug: string,
    projectId: string,
    payload: TStateTransitionPayload
  ): Promise<TStateTransition> {
    return this.unwrap(this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/state-transitions/`, payload));
  }

  deleteTransition(workspaceSlug: string, projectId: string, transitionId: string): Promise<void> {
    return this.unwrap(
      this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/state-transitions/${transitionId}/`)
    );
  }

  // Worklogs --------------------------------------------------------------

  listWorklogs(workspaceSlug: string, projectId: string, issueId: string): Promise<TWorklog[]> {
    return this.unwrap(this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/worklogs/`));
  }

  createWorklog(
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    payload: { duration: number; logged_at: string; description?: string }
  ): Promise<TWorklog> {
    return this.unwrap(
      this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/worklogs/`, payload)
    );
  }

  deleteWorklog(workspaceSlug: string, projectId: string, issueId: string, worklogId: string): Promise<void> {
    return this.unwrap(
      this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/worklogs/${worklogId}/`)
    );
  }

  worklogSummary(workspaceSlug: string, projectId: string, issueId: string): Promise<TWorklogSummary> {
    return this.unwrap(
      this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/worklog-summary/`)
    );
  }

  // Templates -------------------------------------------------------------

  listTemplates(workspaceSlug: string, kind?: TTemplateKind): Promise<TTemplate[]> {
    return this.unwrap(this.get(`/api/workspaces/${workspaceSlug}/templates/`, { params: { kind } }));
  }

  createTemplate(workspaceSlug: string, payload: Partial<TTemplate>): Promise<TTemplate> {
    return this.unwrap(this.post(`/api/workspaces/${workspaceSlug}/templates/`, payload));
  }

  /** Returns the created work item plus any payload keys that could not be resolved. */
  applyTemplate(
    workspaceSlug: string,
    projectId: string,
    templateId: string,
    overrides: Record<string, unknown> = {}
  ): Promise<{ id: string; name: string; dropped: string[] }> {
    return this.unwrap(
      this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/templates/${templateId}/apply/`, overrides)
    );
  }

  // Teamspaces and initiatives --------------------------------------------

  listTeamspaces(workspaceSlug: string): Promise<TTeamspace[]> {
    return this.unwrap(this.get(`/api/workspaces/${workspaceSlug}/teamspaces/`));
  }

  createTeamspace(workspaceSlug: string, payload: { name: string; description?: string }): Promise<TTeamspace> {
    return this.unwrap(this.post(`/api/workspaces/${workspaceSlug}/teamspaces/`, payload));
  }

  /** Omit a key to leave that side of the membership alone. */
  setTeamspaceMembership(
    workspaceSlug: string,
    teamId: string,
    payload: { member_ids?: string[]; project_ids?: string[] }
  ): Promise<TTeamspace> {
    return this.unwrap(this.post(`/api/workspaces/${workspaceSlug}/teamspaces/${teamId}/membership/`, payload));
  }

  listInitiatives(workspaceSlug: string): Promise<TInitiative[]> {
    return this.unwrap(this.get(`/api/workspaces/${workspaceSlug}/initiatives/`));
  }

  createInitiative(workspaceSlug: string, payload: Partial<TInitiative>): Promise<TInitiative> {
    return this.unwrap(this.post(`/api/workspaces/${workspaceSlug}/initiatives/`, payload));
  }

  setInitiativeProjects(
    workspaceSlug: string,
    initiativeId: string,
    projectIds: string[]
  ): Promise<{ project_ids: string[]; dropped: string[] }> {
    return this.unwrap(
      this.post(`/api/workspaces/${workspaceSlug}/initiatives/${initiativeId}/projects/`, {
        project_ids: projectIds,
      })
    );
  }

  initiativeProgress(workspaceSlug: string, initiativeId: string): Promise<TInitiativeProgress> {
    return this.unwrap(this.get(`/api/workspaces/${workspaceSlug}/initiatives/${initiativeId}/progress/`));
  }

  // Dashboards ------------------------------------------------------------

  listDashboards(workspaceSlug: string): Promise<TDashboard[]> {
    return this.unwrap(this.get(`/api/workspaces/${workspaceSlug}/dashboards/`));
  }

  createDashboard(workspaceSlug: string, payload: { name: string; description?: string }): Promise<TDashboard> {
    return this.unwrap(this.post(`/api/workspaces/${workspaceSlug}/dashboards/`, payload));
  }

  listWidgets(workspaceSlug: string, dashboardId: string): Promise<TDashboardWidget[]> {
    return this.unwrap(this.get(`/api/workspaces/${workspaceSlug}/dashboards/${dashboardId}/widgets/`));
  }

  createWidget(
    workspaceSlug: string,
    dashboardId: string,
    payload: Partial<TDashboardWidget>
  ): Promise<TDashboardWidget> {
    return this.unwrap(this.post(`/api/workspaces/${workspaceSlug}/dashboards/${dashboardId}/widgets/`, payload));
  }

  widgetData(workspaceSlug: string, dashboardId: string, widgetId: string): Promise<TDashboardWidgetData> {
    return this.unwrap(
      this.get(`/api/workspaces/${workspaceSlug}/dashboards/${dashboardId}/widgets/${widgetId}/data/`)
    );
  }

  // Automations -----------------------------------------------------------

  listAutomations(workspaceSlug: string, projectId: string): Promise<TAutomation[]> {
    return this.unwrap(this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/automations/`));
  }

  createAutomation(workspaceSlug: string, projectId: string, payload: Partial<TAutomation>): Promise<TAutomation> {
    return this.unwrap(this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/automations/`, payload));
  }

  deleteAutomation(workspaceSlug: string, projectId: string, automationId: string): Promise<void> {
    return this.unwrap(
      this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/automations/${automationId}/`)
    );
  }

  // De-dupe ---------------------------------------------------------------

  /** Returns nothing for a name under five characters: short words predict nothing. */
  findDuplicates(
    workspaceSlug: string,
    projectId: string,
    name: string,
    excludeId?: string
  ): Promise<{ results: TDuplicateCandidate[] }> {
    return this.unwrap(
      this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/de-dupe/`, {
        params: { name, exclude: excludeId },
      })
    );
  }
}
