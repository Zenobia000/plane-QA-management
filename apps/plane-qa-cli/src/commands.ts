import { readFile, writeFile } from "node:fs/promises";
import { basename } from "node:path";

import {
  type DayPart,
  type JsonObject,
  type PlaneQAClient,
  type Project,
  REQUIREMENT_KINDS,
  TEST_CASE_TYPES,
  type TestingExportFormat,
  type TestingSearchScope,
  THRESHOLD_OPERATORS,
  type WorkItem,
} from "@plane/qa-sdk";

import {
  booleanOption,
  commaListOption,
  enumListOption,
  enumOption,
  jsonOption,
  numberOption,
  optionString,
  type ParsedArguments,
  requiredOption,
} from "./arguments";
import type { CLIConfig } from "./config";

const projectFor = async (client: PlaneQAClient, config: CLIConfig): Promise<Project> => {
  if (!config.project) throw new Error("Project is required through --project or PLANE_PROJECT.");
  return client.resolveProject(config.workspace, config.project);
};

const issueFor = async (
  client: PlaneQAClient,
  config: CLIConfig,
  project: Project,
  reference: string
): Promise<WorkItem> => client.resolveIssue(config.workspace, project.id, reference);

const requireConfirmation = (args: ParsedArguments, operation: string) => {
  if (args.options.yes !== true && args.options.dry_run !== true) {
    throw new Error(`${operation} requires explicit --yes confirmation.`);
  }
};

const dryRunReceipt = (args: ParsedArguments, operation: string, target: Record<string, unknown>) =>
  args.options.dry_run === true ? { dry_run: true, operation, target } : undefined;

const compact = (input: Record<string, unknown>): Record<string, unknown> =>
  Object.fromEntries(Object.entries(input).filter(([, value]) => value !== undefined));

/**
 * The four threshold columns, present together or absent together.
 *
 * Emitted as a group rather than four independent options because clearing a threshold means
 * sending all four -- `compact` drops undefined, so a lone `--threshold-value ""` would reach
 * the server as a partial threshold and be rejected there with a message about a field the
 * caller did not think they were touching. Passing any of the four sends all four; passing
 * none sends nothing, which leaves whatever the current version holds.
 */
const thresholdOptions = (args: ParsedArguments): Record<string, unknown> => {
  const metric = optionString(args.options, "threshold_metric");
  const operator = enumOption(args.options, "threshold_operator", THRESHOLD_OPERATORS);
  const value = numberOption(args.options, "threshold_value");
  const unit = optionString(args.options, "threshold_unit");
  if (metric === undefined && operator === undefined && value === undefined && unit === undefined) return {};
  return {
    threshold_metric: metric ?? "",
    threshold_operator: operator ?? "",
    threshold_value: value ?? null,
    threshold_unit: unit ?? "",
  };
};

export const executeCommand = async (
  client: PlaneQAClient,
  config: CLIConfig,
  args: ParsedArguments
): Promise<unknown> => {
  const [group, action] = args.positionals;
  if (!group || !action) throw new Error("A command group and action are required. Run plane-qa --help.");

  if (group === "project") {
    if (action === "list") return client.listProjects(config.workspace);
    const project = await projectFor(client, config);
    if (action === "get") return project;
    if (action === "states") return client.listStates(config.workspace, project.id);
    if (action === "update") {
      return client.updateProject(
        config.workspace,
        project.id,
        compact({
          name: optionString(args.options, "name"),
          description: optionString(args.options, "description"),
          ...jsonOption(args.options, "body", {}),
        })
      );
    }
  }

  // Availability is workspace-scoped, so none of these resolve a project first.
  if (group === "availability") {
    if (action === "schedule") {
      return client.getAvailabilitySchedule(
        config.workspace,
        requiredOption(args.options, "from"),
        requiredOption(args.options, "to"),
        optionString(args.options, "members")?.split(",").filter(Boolean)
      );
    }
    if (action === "overlap") {
      return client.findAvailabilityOverlap(config.workspace, {
        member_ids: requiredOption(args.options, "members").split(",").filter(Boolean),
        date_from: requiredOption(args.options, "from"),
        date_to: requiredOption(args.options, "to"),
        duration_minutes: Number(optionString(args.options, "duration") ?? 30),
      });
    }
    if (action === "calendars") return client.listWorkCalendars(config.workspace);
    if (action === "leave-types") return client.listLeaveTypes(config.workspace);
    if (action === "leaves") {
      return client.listLeaves(
        config.workspace,
        requiredOption(args.options, "from"),
        requiredOption(args.options, "to"),
        optionString(args.options, "members")?.split(",").filter(Boolean)
      );
    }
    if (action === "request-leave") {
      // Built field by field rather than through `compact`, which widens to
      // Record<string, unknown> and would need a cast that hides a real mismatch.
      const startPart = optionString(args.options, "start_part") as DayPart | undefined;
      const endPart = optionString(args.options, "end_part") as DayPart | undefined;
      return client.createLeave(config.workspace, {
        leave_type: requiredOption(args.options, "type"),
        start_date: requiredOption(args.options, "from"),
        end_date: requiredOption(args.options, "to"),
        ...(startPart ? { start_day_part: startPart } : {}),
        ...(endPart ? { end_day_part: endPart } : {}),
        ...(optionString(args.options, "reason") ? { reason: optionString(args.options, "reason") } : {}),
        ...(optionString(args.options, "member") ? { member: optionString(args.options, "member") } : {}),
      });
    }
    if (action === "cancel-leave") {
      requireConfirmation(args, "leave cancel");
      const leaveId = requiredOption(args.options, "id");
      const preview = dryRunReceipt(args, "leave cancel", { id: leaveId });
      if (preview) return preview;
      return client.cancelLeave(config.workspace, leaveId);
    }
    if (action === "events") {
      return client.listTeamEvents(
        config.workspace,
        requiredOption(args.options, "from"),
        requiredOption(args.options, "to")
      );
    }
    if (action === "profiles") return client.listWorkProfiles(config.workspace);
    if (action === "set-profile") {
      return client.updateWorkProfile(
        config.workspace,
        requiredOption(args.options, "member"),
        compact({
          work_calendar: optionString(args.options, "calendar"),
          timezone: optionString(args.options, "timezone"),
          work_start_time: optionString(args.options, "start"),
          work_end_time: optionString(args.options, "end"),
          core_hours_start: optionString(args.options, "core_start"),
          core_hours_end: optionString(args.options, "core_end"),
          hours_per_day: optionString(args.options, "hours"),
          approver: optionString(args.options, "approver"),
          clear_core_hours: args.options.clear_core_hours === true ? true : undefined,
        })
      );
    }
  }

  if (group === "initiative") {
    if (action === "list") return client.listInitiatives(config.workspace);
    if (action === "create") {
      return client.createInitiative(
        config.workspace,
        compact({
          name: requiredOption(args.options, "name"),
          description: optionString(args.options, "description"),
          target_date: optionString(args.options, "target_date"),
          status: optionString(args.options, "status"),
          sort_order: numberOption(args.options, "sort_order"),
          project_ids: commaListOption(args.options, "project_ids"),
          ...jsonOption(args.options, "body", {}),
        })
      );
    }
  }

  const project = await projectFor(client, config);

  if (group === "search" && action === "query") {
    return client.searchTesting(
      config.workspace,
      project.id,
      optionString(args.options, "query", "") ?? "",
      (optionString(args.options, "scope", "all") ?? "all") as TestingSearchScope
    );
  }

  if (group === "export" && action === "testing") {
    const outputPath = requiredOption(args.options, "output");
    const format = (optionString(args.options, "format", "csv") ?? "csv") as TestingExportFormat;
    const content = await client.exportTesting(
      config.workspace,
      project.id,
      optionString(args.options, "query", "") ?? "",
      (optionString(args.options, "scope", "all") ?? "all") as TestingSearchScope,
      format
    );
    await writeFile(outputPath, content, typeof content === "string" ? "utf8" : undefined);
    return { exported: true, format, output: outputPath };
  }

  if (group === "type") {
    if (action === "list") return client.listWorkItemTypes(config.workspace);
    if (action === "create") {
      return client.createProjectWorkItemType(
        config.workspace,
        project.id,
        compact({
          name: requiredOption(args.options, "name"),
          description: optionString(args.options, "description"),
          is_epic: args.options.is_epic === true ? true : undefined,
          is_default: args.options.is_default === true ? true : undefined,
          level: numberOption(args.options, "level"),
          ...jsonOption(args.options, "body", {}),
        })
      );
    }
  }

  if (group === "property") {
    if (action === "list") return client.listWorkItemProperties(config.workspace, project.id);
    if (action === "create") {
      return client.createWorkItemProperty(
        config.workspace,
        project.id,
        compact({
          name: requiredOption(args.options, "name"),
          kind: requiredOption(args.options, "kind"),
          description: optionString(args.options, "description"),
          is_required: args.options.is_required === true ? true : undefined,
          sort_order: numberOption(args.options, "sort_order"),
          default_value: jsonOption(args.options, "default_value", undefined),
          options: jsonOption(args.options, "options", undefined),
          ...jsonOption(args.options, "body", {}),
        })
      );
    }
    if (action === "set") {
      const issue = await issueFor(client, config, project, requiredOption(args.options, "issue"));
      return client.setWorkItemPropertyValue(
        config.workspace,
        project.id,
        issue.id,
        requiredOption(args.options, "property_id"),
        jsonOption(args.options, "value", null)
      );
    }
  }

  if (group === "milestone") {
    if (action === "list") return client.listMilestones(config.workspace, project.id);
    if (action === "create") {
      return client.createMilestone(
        config.workspace,
        project.id,
        compact({
          name: requiredOption(args.options, "name"),
          description: optionString(args.options, "description"),
          target_date: optionString(args.options, "target_date"),
          status: optionString(args.options, "status"),
          sort_order: numberOption(args.options, "sort_order"),
          ...jsonOption(args.options, "body", {}),
        })
      );
    }
  }

  if (group === "issue") {
    if (action === "list") {
      return client.listIssues(
        config.workspace,
        project.id,
        compact({
          state: optionString(args.options, "state"),
          priority: optionString(args.options, "priority"),
          leaf_only: booleanOption(args.options, "leaf_only"),
          requirement_kind: enumListOption(args.options, "requirement_kind", REQUIREMENT_KINDS),
          per_page: numberOption(args.options, "per_page"),
        }) as Record<string, string | number | boolean>
      );
    }
    if (action === "create") {
      return client.createIssue(
        config.workspace,
        project.id,
        compact({
          name: requiredOption(args.options, "name"),
          state_id: optionString(args.options, "state_id"),
          priority: optionString(args.options, "priority"),
          description_html: optionString(args.options, "description"),
          requirement_kind: enumOption(args.options, "requirement_kind", REQUIREMENT_KINDS),
          ...jsonOption(args.options, "body", {}),
        })
      );
    }
    const reference = requiredOption(args.options, "issue");
    const issue = await issueFor(client, config, project, reference);
    if (action === "get") return issue;
    if (action === "update" || action === "transition") {
      return client.updateIssue(
        config.workspace,
        project.id,
        issue.id,
        compact({
          name: optionString(args.options, "name"),
          state_id: optionString(args.options, "state_id"),
          priority: optionString(args.options, "priority"),
          description_html: optionString(args.options, "description"),
          requirement_kind: enumOption(args.options, "requirement_kind", REQUIREMENT_KINDS),
          ...jsonOption(args.options, "body", {}),
        })
      );
    }
    if (action === "comment") {
      return client.addIssueComment(config.workspace, project.id, issue.id, {
        comment_html: requiredOption(args.options, "body"),
      });
    }
    if (action === "archive") {
      requireConfirmation(args, "issue archive");
      const preview = dryRunReceipt(args, "issue archive", { id: issue.id });
      if (preview) return preview;
      await client.archiveIssue(config.workspace, project.id, issue.id);
      return { archived: true, id: issue.id };
    }
  }

  if (group === "folder") {
    if (action === "list") return client.listFolders(config.workspace, project.id);
    if (action === "create") {
      return client.createFolder(
        config.workspace,
        project.id,
        compact({
          name: requiredOption(args.options, "name"),
          parent_id: optionString(args.options, "parent_id"),
          sort_order: numberOption(args.options, "sort_order"),
        }) as { name: string; parent_id?: string; sort_order?: number }
      );
    }
    const folderId = requiredOption(args.options, "folder");
    if (action === "get") return client.getFolder(config.workspace, project.id, folderId);
    if (action === "update") {
      return client.updateFolder(
        config.workspace,
        project.id,
        folderId,
        compact({
          name: optionString(args.options, "name"),
          parent_id: optionString(args.options, "parent_id"),
          sort_order: numberOption(args.options, "sort_order"),
        })
      );
    }
    if (action === "delete") {
      requireConfirmation(args, "folder delete");
      const preview = dryRunReceipt(args, "folder delete", { id: folderId });
      if (preview) return preview;
      await client.deleteFolder(config.workspace, project.id, folderId);
      return { deleted: true, id: folderId };
    }
  }

  if (group === "view") {
    // Omitting --project makes it a workspace view spanning every project.
    const scope = args.options.workspace_level ? undefined : project.id;
    if (action === "list") return client.listViews(config.workspace, scope);
    if (action === "create") {
      return client.createView(
        config.workspace,
        compact({
          name: requiredOption(args.options, "name"),
          description: optionString(args.options, "description"),
          filters: jsonOption(args.options, "filters", undefined),
          display_filters: jsonOption(args.options, "display_filters", undefined),
          display_properties: jsonOption(args.options, "display_properties", undefined),
          access: numberOption(args.options, "access"),
        }) as { name: string },
        scope
      );
    }
    const viewId = requiredOption(args.options, "view");
    if (action === "get") return client.getView(config.workspace, viewId, scope);
    if (action === "update") {
      return client.updateView(
        config.workspace,
        viewId,
        compact({
          name: optionString(args.options, "name"),
          description: optionString(args.options, "description"),
          filters: jsonOption(args.options, "filters", undefined),
          display_filters: jsonOption(args.options, "display_filters", undefined),
          display_properties: jsonOption(args.options, "display_properties", undefined),
          access: numberOption(args.options, "access"),
          is_locked: args.options.lock ? true : undefined,
        }),
        scope
      );
    }
    if (action === "delete") {
      requireConfirmation(args, "view delete");
      const preview = dryRunReceipt(args, "view delete", { id: viewId });
      if (preview) return preview;
      await client.deleteView(config.workspace, viewId, scope);
      return { deleted: true, id: viewId };
    }
  }

  if (group === "case") {
    if (action === "list") {
      return client.listTestCases(
        config.workspace,
        project.id,
        compact({
          search: optionString(args.options, "search"),
          folder_id: optionString(args.options, "folder_id"),
          work_item_id: optionString(args.options, "issue_id"),
          per_page: numberOption(args.options, "per_page"),
        }) as Record<string, string | number>
      );
    }
    if (action === "create") {
      return client.createTestCase(
        config.workspace,
        project.id,
        compact({
          title: requiredOption(args.options, "title"),
          folder_id: optionString(args.options, "folder_id"),
          priority: optionString(args.options, "priority"),
          case_type: enumOption(args.options, "case_type", TEST_CASE_TYPES),
          description: jsonOption(args.options, "description", undefined),
          preconditions: jsonOption(args.options, "preconditions", undefined),
          ...thresholdOptions(args),
          tags: commaListOption(args.options, "tags"),
          steps: jsonOption(args.options, "steps", undefined),
          ...jsonOption(args.options, "body", {}),
        })
      );
    }
    const caseId = requiredOption(args.options, "case");
    if (action === "get") return client.getTestCase(config.workspace, project.id, caseId);
    if (action === "attachments") {
      return client.listTestCaseAttachments(config.workspace, project.id, caseId);
    }
    if (action === "attach") {
      const filePath = requiredOption(args.options, "file");
      const content = await readFile(filePath);
      return client.uploadTestCaseAttachment(config.workspace, project.id, caseId, {
        name: optionString(args.options, "name", basename(filePath)) ?? basename(filePath),
        type: requiredOption(args.options, "mime_type"),
        content: new Blob([new Uint8Array(content)]),
      });
    }
    if (action === "detach") {
      const attachmentId = requiredOption(args.options, "attachment");
      requireConfirmation(args, "test case attachment delete");
      const preview = dryRunReceipt(args, "test case attachment delete", {
        case_id: caseId,
        attachment_id: attachmentId,
      });
      if (preview) return preview;
      await client.deleteTestCaseAttachment(config.workspace, project.id, caseId, attachmentId);
      return { deleted: true, case_id: caseId, attachment_id: attachmentId };
    }
    if (action === "version") {
      const version = numberOption(args.options, "version");
      if (!version) throw new Error("--version must be a positive number.");
      return client.getTestCaseVersion(config.workspace, project.id, caseId, version);
    }
    if (action === "update") {
      return client.updateTestCase(
        config.workspace,
        project.id,
        caseId,
        compact({
          title: optionString(args.options, "title"),
          folder_id: optionString(args.options, "folder_id"),
          priority: optionString(args.options, "priority"),
          case_type: enumOption(args.options, "case_type", TEST_CASE_TYPES),
          description: jsonOption(args.options, "description", undefined),
          preconditions: jsonOption(args.options, "preconditions", undefined),
          ...thresholdOptions(args),
          steps: jsonOption(args.options, "steps", undefined),
          ...jsonOption(args.options, "body", {}),
        })
      );
    }
    if (action === "link-issue") {
      const issue = await issueFor(client, config, project, requiredOption(args.options, "issue"));
      return client.linkTestCase(config.workspace, project.id, caseId, issue.id);
    }
    if (action === "unlink-issue") {
      const issue = await issueFor(client, config, project, requiredOption(args.options, "issue"));
      requireConfirmation(args, "test case unlink");
      const preview = dryRunReceipt(args, "test case unlink", { case_id: caseId, issue_id: issue.id });
      if (preview) return preview;
      await client.unlinkTestCase(config.workspace, project.id, caseId, issue.id);
      return { unlinked: true, case_id: caseId, issue_id: issue.id };
    }
    if (action === "archive") {
      requireConfirmation(args, "test case archive");
      const preview = dryRunReceipt(args, "test case archive", { id: caseId });
      if (preview) return preview;
      await client.archiveTestCase(config.workspace, project.id, caseId);
      return { archived: true, id: caseId };
    }
  }

  if (group === "run") {
    if (action === "list") return client.listTestRuns(config.workspace, project.id);
    if (action === "create") {
      return client.createTestRun(
        config.workspace,
        project.id,
        compact({
          name: requiredOption(args.options, "name"),
          build: optionString(args.options, "build"),
          test_case_ids: commaListOption(args.options, "cases"),
          configuration: jsonOption(args.options, "configuration", {}),
          ...jsonOption(args.options, "body", {}),
        })
      );
    }
    const runId = requiredOption(args.options, "run");
    if (action === "get") return client.getTestRun(config.workspace, project.id, runId);
    if (action === "record-result") {
      return client.recordTestResult(
        config.workspace,
        project.id,
        runId,
        requiredOption(args.options, "run_case"),
        compact({
          status: requiredOption(args.options, "status"),
          actual_result: jsonOption(args.options, "actual", {}),
          duration_ms: numberOption(args.options, "duration_ms"),
        })
      );
    }
    if (action === "create-defect") {
      return client.createDefect(
        config.workspace,
        project.id,
        runId,
        requiredOption(args.options, "run_case"),
        requiredOption(args.options, "result"),
        compact({ name: optionString(args.options, "name") })
      );
    }
    if (action === "close") {
      requireConfirmation(args, "test run close");
      const preview = dryRunReceipt(args, "test run close", { id: runId });
      if (preview) return preview;
      return client.closeTestRun(config.workspace, project.id, runId);
    }
  }

  if (group === "quality") {
    const overview = await client.getQualityOverview(config.workspace, project.id);
    if (action === "overview") return overview;
    if (action === "release-gate") return overview.release_gate;
    if (action === "open-defects") return { open_defects: overview.open_defects };
    if (action === "coverage") return client.getRequirementCoverage(config.workspace, project.id);
  }

  if (group === "automation") {
    const idempotencyKey = requiredOption(args.options, "idempotency_key");
    if (action === "upload-junit") {
      const junitXml = await readFile(requiredOption(args.options, "file"), "utf8");
      return client.ingestAutomation(config.workspace, project.id, idempotencyKey, {
        format: "junit",
        source: optionString(args.options, "source", "plane-qa-cli") ?? "plane-qa-cli",
        name: requiredOption(args.options, "name"),
        build: optionString(args.options, "build", "") ?? "",
        configuration: jsonOption(args.options, "configuration", {}),
        artifact_ids: commaListOption(args.options, "artifact_ids"),
        junit_xml: junitXml,
      });
    }
    if (action === "upload-results") {
      const payload = JSON.parse(await readFile(requiredOption(args.options, "file"), "utf8")) as JsonObject;
      return client.ingestAutomation(config.workspace, project.id, idempotencyKey, payload);
    }
  }

  throw new Error(`Unknown command: ${group} ${action}. Run plane-qa --help.`);
};
