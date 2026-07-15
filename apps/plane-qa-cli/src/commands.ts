import { readFile } from "node:fs/promises";

import type { JsonObject, PlaneQAClient, Project, WorkItem } from "@plane/qa-sdk";

import {
  commaListOption,
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

  const project = await projectFor(client, config);

  if (group === "issue") {
    if (action === "list") {
      return client.listIssues(
        config.workspace,
        project.id,
        compact({
          state: optionString(args.options, "state"),
          priority: optionString(args.options, "priority"),
          per_page: numberOption(args.options, "per_page"),
        }) as Record<string, string | number>
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
          description: jsonOption(args.options, "description", undefined),
          preconditions: jsonOption(args.options, "preconditions", undefined),
          tags: commaListOption(args.options, "tags"),
          steps: jsonOption(args.options, "steps", undefined),
          ...jsonOption(args.options, "body", {}),
        })
      );
    }
    const caseId = requiredOption(args.options, "case");
    if (action === "get") return client.getTestCase(config.workspace, project.id, caseId);
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
          description: jsonOption(args.options, "description", undefined),
          preconditions: jsonOption(args.options, "preconditions", undefined),
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
