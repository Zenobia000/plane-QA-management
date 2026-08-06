import { errorKindForStatus, PlaneQAError } from "./errors";
import { paginatedSchema, parsePlaneResponse, projectSchema, testingCapabilitiesSchema } from "./schemas";
import type {
  AllocationMatrix,
  CalendarDay,
  CalendarDayInput,
  AvailabilitySchedule,
  CycleCapacity,
  LeaveType,
  MemberLeave,
  MemberLeaveInput,
  TeamEvent,
  MemberWorkProfile,
  OverlapRequest,
  OverlapResult,
  WorkCalendar,
  SavedView,
  SavedViewInput,
  JsonObject,
  JsonValue,
  PaginatedResponse,
  PlaneQAClientOptions,
  Project,
  RequestOptions,
  State,
  TestCase,
  TestCaseAttachment,
  TestCaseAttachmentUploadResponse,
  TestCaseLink,
  TestCaseVersion,
  TestFolder,
  TestResult,
  TestRun,
  TestingCapabilities,
  TestingExportFormat,
  TestingSearchResponse,
  TestingSearchScope,
  WorkItem,
  WorkItemProperty,
  WorkItemType,
  Initiative,
  Milestone,
} from "./types";

const RETRYABLE_STATUS = new Set([429, 502, 503, 504]);
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const ISSUE_IDENTIFIER_PATTERN = /^[A-Z][A-Z0-9_]*-\d+$/i;

const sleep = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds));

const encodePath = (value: string) => encodeURIComponent(value);

const parseRetryAfter = (value: string | null): number | undefined => {
  if (!value) return undefined;
  const seconds = Number(value);
  if (!Number.isNaN(seconds)) return Math.max(0, seconds * 1000);
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? undefined : Math.max(0, timestamp - Date.now());
};

const errorMessage = (payload: unknown, fallback: string): string => {
  if (payload && typeof payload === "object") {
    for (const key of ["error", "message", "detail"]) {
      const value = (payload as Record<string, unknown>)[key];
      if (typeof value === "string" && value.trim()) return value;
      if (value && typeof value === "object") {
        const nested = (value as Record<string, unknown>).message;
        if (typeof nested === "string" && nested.trim()) return nested;
      }
    }
  }
  return fallback;
};

export class PlaneQAClient {
  readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly fetcher: typeof fetch;
  private readonly timeoutMs: number;
  private readonly maxRetries: number;
  private readonly retryBaseDelayMs: number;

  constructor(options: PlaneQAClientOptions) {
    if (!options.baseUrl.trim()) throw new PlaneQAError({ kind: "validation", message: "baseUrl is required." });
    if (!options.apiKey.trim()) throw new PlaneQAError({ kind: "validation", message: "apiKey is required." });
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.apiKey = options.apiKey;
    this.fetcher = options.fetch ?? globalThis.fetch;
    this.timeoutMs = options.timeoutMs ?? 15_000;
    this.maxRetries = options.maxRetries ?? 3;
    this.retryBaseDelayMs = options.retryBaseDelayMs ?? 250;
  }

  async request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
    const url = new URL(`${this.baseUrl}${path}`);
    for (const [key, value] of Object.entries(options.query ?? {})) {
      if (value !== undefined && value !== null) url.searchParams.set(key, String(value));
    }
    const mayRetry = options.idempotent ?? ["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase());

    // Retries are intentionally sequential: each attempt depends on the prior response and backoff.
    // oxlint-disable no-await-in-loop
    for (let attempt = 0; attempt <= this.maxRetries; attempt += 1) {
      const timeout = AbortSignal.timeout(this.timeoutMs);
      const signal = options.signal ? AbortSignal.any([options.signal, timeout]) : timeout;
      let response: Response;
      try {
        response = await this.fetcher(url, {
          method,
          signal,
          headers: {
            Accept: "application/json",
            "X-API-Key": this.apiKey,
            ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
            ...options.headers,
          },
          body: options.body === undefined ? undefined : JSON.stringify(options.body),
        });
      } catch (cause) {
        if (mayRetry && attempt < this.maxRetries) {
          await sleep(this.retryBaseDelayMs * 2 ** attempt);
          continue;
        }
        throw new PlaneQAError({
          kind: "network",
          message:
            cause instanceof Error && cause.name === "TimeoutError" ? "Request timed out." : "Network request failed.",
          retryable: true,
          cause,
        });
      }

      const contentType = response.headers.get("content-type") ?? "";
      const payload =
        response.ok && options.responseType === "array_buffer"
          ? new Uint8Array(await response.arrayBuffer())
          : response.status === 204
            ? undefined
            : contentType.includes("application/json")
              ? await response.json()
              : await response.text();
      if (response.ok) return payload as T;

      if (mayRetry && RETRYABLE_STATUS.has(response.status) && attempt < this.maxRetries) {
        await sleep(parseRetryAfter(response.headers.get("retry-after")) ?? this.retryBaseDelayMs * 2 ** attempt);
        continue;
      }
      throw new PlaneQAError({
        kind: errorKindForStatus(response.status),
        status: response.status,
        message: errorMessage(payload, `Plane QA request failed with HTTP ${response.status}.`),
        details: payload,
        retryable: RETRYABLE_STATUS.has(response.status),
      });
    }
    // oxlint-enable no-await-in-loop
    throw new PlaneQAError({ kind: "network", message: "Retry budget exhausted.", retryable: true });
  }

  private apiPath(workspace: string, suffix: string): string {
    return `/api/v1/workspaces/${encodePath(workspace)}${suffix}`;
  }

  private projectPath(workspace: string, projectId: string, suffix = ""): string {
    return this.apiPath(workspace, `/projects/${encodePath(projectId)}${suffix}`);
  }

  private testingPath(workspace: string, projectId: string, suffix: string): string {
    return this.projectPath(workspace, projectId, `/testing${suffix}`);
  }

  /**
   * Saved views.
   *
   * Send `filters`; the server compiles `query` from it, so callers never write
   * the internal lookup syntax. Passing a project scopes the view to it; omitting
   * one creates a workspace view spanning every project.
   */
  listViews(workspace: string, projectId?: string): Promise<SavedView[]> {
    return this.request(
      "GET",
      projectId ? this.projectPath(workspace, projectId, "/views/") : this.apiPath(workspace, "/views/")
    );
  }

  getView(workspace: string, viewId: string, projectId?: string): Promise<SavedView> {
    return this.request(
      "GET",
      projectId
        ? this.projectPath(workspace, projectId, `/views/${encodePath(viewId)}/`)
        : this.apiPath(workspace, `/views/${encodePath(viewId)}/`)
    );
  }

  createView(workspace: string, input: SavedViewInput, projectId?: string): Promise<SavedView> {
    return this.request(
      "POST",
      projectId ? this.projectPath(workspace, projectId, "/views/") : this.apiPath(workspace, "/views/"),
      { body: input }
    );
  }

  updateView(
    workspace: string,
    viewId: string,
    input: Partial<SavedViewInput>,
    projectId?: string
  ): Promise<SavedView> {
    return this.request(
      "PATCH",
      projectId
        ? this.projectPath(workspace, projectId, `/views/${encodePath(viewId)}/`)
        : this.apiPath(workspace, `/views/${encodePath(viewId)}/`),
      { body: input }
    );
  }

  deleteView(workspace: string, viewId: string, projectId?: string): Promise<void> {
    return this.request(
      "DELETE",
      projectId
        ? this.projectPath(workspace, projectId, `/views/${encodePath(viewId)}/`)
        : this.apiPath(workspace, `/views/${encodePath(viewId)}/`)
    );
  }

  listProjects(workspace: string, query: RequestOptions["query"] = {}): Promise<PaginatedResponse<Project>> {
    return this.request("GET", this.apiPath(workspace, "/projects/"), { query: { per_page: 100, ...query } }).then(
      (payload) =>
        parsePlaneResponse(paginatedSchema(projectSchema), payload, "listProjects") as PaginatedResponse<Project>
    );
  }

  getProject(workspace: string, projectId: string): Promise<Project> {
    return this.request("GET", this.projectPath(workspace, projectId, "/")).then(
      (payload) => parsePlaneResponse(projectSchema, payload, "getProject") as Project
    );
  }

  updateProject(workspace: string, projectId: string, input: Record<string, unknown>): Promise<Project> {
    return this.request("PATCH", this.projectPath(workspace, projectId, "/"), { body: input });
  }

  async resolveProject(workspace: string, projectReference: string): Promise<Project> {
    if (UUID_PATTERN.test(projectReference)) return this.getProject(workspace, projectReference);
    const page = await this.listProjects(workspace);
    const project = page.results.find((item) => item.identifier.toLowerCase() === projectReference.toLowerCase());
    if (!project) {
      throw new PlaneQAError({ kind: "not_found", status: 404, message: `Project ${projectReference} was not found.` });
    }
    return project;
  }

  /**
   * Team availability.
   *
   * Workspace-scoped, unlike everything above it: an absence is a fact about a person, not
   * about a project. See ADR 0008.
   */
  getAvailabilitySchedule(
    workspace: string,
    from: string,
    to: string,
    memberIds?: string[]
  ): Promise<AvailabilitySchedule> {
    return this.request("GET", this.apiPath(workspace, "/availability/schedule/"), {
      query: { from, to, ...(memberIds?.length ? { member_ids: memberIds.join(",") } : {}) },
    });
  }

  /** POST for a read: the member list is the request, and it can be long. Nothing is written. */
  findAvailabilityOverlap(workspace: string, input: OverlapRequest): Promise<OverlapResult> {
    return this.request("POST", this.apiPath(workspace, "/availability/overlap/"), {
      body: input,
      idempotent: true,
    });
  }

  listWorkCalendars(workspace: string): Promise<WorkCalendar[]> {
    return this.request("GET", this.apiPath(workspace, "/availability/calendars/"));
  }

  listWorkProfiles(workspace: string): Promise<MemberWorkProfile[]> {
    return this.request("GET", this.apiPath(workspace, "/availability/profiles/"));
  }

  updateWorkProfile(
    workspace: string,
    memberId: string,
    input: Partial<MemberWorkProfile> & { clear_core_hours?: boolean }
  ): Promise<MemberWorkProfile> {
    return this.request("PATCH", this.apiPath(workspace, `/availability/profiles/${encodePath(memberId)}/`), {
      body: input,
    });
  }

  listLeaveTypes(workspace: string): Promise<LeaveType[]> {
    return this.request("GET", this.apiPath(workspace, "/availability/leave-types/"));
  }

  listLeaves(workspace: string, from: string, to: string, memberIds?: string[]): Promise<MemberLeave[]> {
    return this.request("GET", this.apiPath(workspace, "/availability/leaves/"), {
      query: { from, to, ...(memberIds?.length ? { member_ids: memberIds.join(",") } : {}) },
    });
  }

  createLeave(workspace: string, input: MemberLeaveInput): Promise<MemberLeave> {
    return this.request("POST", this.apiPath(workspace, "/availability/leaves/"), { body: input });
  }

  cancelLeave(workspace: string, leaveId: string): Promise<MemberLeave> {
    return this.request("PATCH", this.apiPath(workspace, `/availability/leaves/${encodePath(leaveId)}/`), {
      body: { action: "cancel" },
    });
  }

  listTeamEvents(workspace: string, from: string, to: string): Promise<TeamEvent[]> {
    return this.request("GET", this.apiPath(workspace, "/availability/events/"), { query: { from, to } });
  }

  listPendingLeaves(workspace: string): Promise<MemberLeave[]> {
    return this.request("GET", this.apiPath(workspace, "/availability/leaves/pending/"));
  }

  decideLeave(workspace: string, leaveId: string, action: "approve" | "reject", note = ""): Promise<MemberLeave> {
    return this.request("PATCH", this.apiPath(workspace, `/availability/leaves/${encodePath(leaveId)}/`), {
      body: { action, note },
    });
  }

  getAllocations(workspace: string): Promise<AllocationMatrix> {
    return this.request("GET", this.apiPath(workspace, "/availability/allocations/"));
  }

  setAllocation(
    workspace: string,
    memberId: string,
    projectId: string,
    percent: number
  ): Promise<{ member_id: string; project_id: string; allocation_percent: number }> {
    return this.request("PUT", this.apiPath(workspace, "/availability/allocations/"), {
      body: { member_id: memberId, project_id: projectId, allocation_percent: percent },
    });
  }

  getCycleCapacity(workspace: string, projectId: string, cycleId: string): Promise<CycleCapacity> {
    return this.request("GET", this.projectPath(workspace, projectId, `/cycles/${encodePath(cycleId)}/capacity/`));
  }

  listCalendarDays(workspace: string, calendarId: string, year?: number): Promise<CalendarDay[]> {
    return this.request("GET", this.apiPath(workspace, `/availability/calendars/${encodePath(calendarId)}/days/`), {
      query: year ? { year } : {},
    });
  }

  /** The path a published national calendar arrives through, once a year. */
  setCalendarDays(
    workspace: string,
    calendarId: string,
    days: CalendarDayInput[],
    replaceYear?: number
  ): Promise<CalendarDay[]> {
    return this.request("POST", this.apiPath(workspace, `/availability/calendars/${encodePath(calendarId)}/days/`), {
      body: { days, ...(replaceYear ? { replace_year: replaceYear } : {}) },
    });
  }

  updateWorkCalendar(workspace: string, calendarId: string, input: Partial<WorkCalendar>): Promise<WorkCalendar> {
    return this.request("PATCH", this.apiPath(workspace, `/availability/calendars/${encodePath(calendarId)}/`), {
      body: input,
    });
  }

  updateLeaveType(workspace: string, typeId: string, input: Partial<LeaveType>): Promise<LeaveType> {
    return this.request("PATCH", this.apiPath(workspace, `/availability/leave-types/${encodePath(typeId)}/`), {
      body: input,
    });
  }

  listStates(workspace: string, projectId: string): Promise<PaginatedResponse<State> | State[]> {
    return this.request("GET", this.projectPath(workspace, projectId, "/states/"), { query: { per_page: 100 } });
  }

  listIssues(
    workspace: string,
    projectId: string,
    query: RequestOptions["query"] = {}
  ): Promise<PaginatedResponse<WorkItem>> {
    return this.request("GET", this.projectPath(workspace, projectId, "/work-items/"), { query });
  }

  getIssue(workspace: string, projectId: string, issueId: string): Promise<WorkItem> {
    return this.request("GET", this.projectPath(workspace, projectId, `/work-items/${encodePath(issueId)}/`));
  }

  getIssueByIdentifier(workspace: string, identifier: string): Promise<WorkItem> {
    return this.request("GET", this.apiPath(workspace, `/work-items/${encodePath(identifier)}/`));
  }

  resolveIssue(workspace: string, projectId: string, reference: string): Promise<WorkItem> {
    return ISSUE_IDENTIFIER_PATTERN.test(reference)
      ? this.getIssueByIdentifier(workspace, reference)
      : this.getIssue(workspace, projectId, reference);
  }

  createIssue(workspace: string, projectId: string, input: Record<string, unknown>): Promise<WorkItem> {
    return this.request("POST", this.projectPath(workspace, projectId, "/work-items/"), { body: input });
  }

  listWorkItemTypes(workspace: string): Promise<PaginatedResponse<WorkItemType>> {
    return this.request("GET", this.apiPath(workspace, "/work-item-types/"), { query: { per_page: 100 } });
  }

  createWorkItemType(workspace: string, input: Record<string, unknown>): Promise<WorkItemType> {
    return this.request("POST", this.apiPath(workspace, "/work-item-types/"), { body: input });
  }

  enableWorkItemType(
    workspace: string,
    projectId: string,
    input: { type_id: string; level?: number; is_default?: boolean }
  ): Promise<Record<string, unknown>> {
    return this.request("POST", this.projectPath(workspace, projectId, "/work-item-types/"), { body: input });
  }

  async createProjectWorkItemType(
    workspace: string,
    projectId: string,
    input: Record<string, unknown>
  ): Promise<WorkItemType> {
    const workItemType = await this.createWorkItemType(workspace, input);
    try {
      await this.enableWorkItemType(workspace, projectId, {
        type_id: workItemType.id,
        level: typeof input.level === "number" ? input.level : undefined,
        is_default: input.is_default === true,
      });
      return workItemType;
    } catch (error) {
      await this.request("DELETE", this.apiPath(workspace, `/work-item-types/${encodePath(workItemType.id)}/`)).catch(
        () => undefined
      );
      throw error;
    }
  }

  listWorkItemProperties(workspace: string, projectId: string): Promise<PaginatedResponse<WorkItemProperty>> {
    return this.request("GET", this.projectPath(workspace, projectId, "/work-item-properties/"), {
      query: { per_page: 100 },
    });
  }

  createWorkItemProperty(
    workspace: string,
    projectId: string,
    input: Record<string, unknown>
  ): Promise<WorkItemProperty> {
    return this.request("POST", this.projectPath(workspace, projectId, "/work-item-properties/"), { body: input });
  }

  setWorkItemPropertyValue(
    workspace: string,
    projectId: string,
    issueId: string,
    propertyId: string,
    value: JsonValue
  ): Promise<Record<string, unknown>> {
    return this.request(
      "PUT",
      this.projectPath(
        workspace,
        projectId,
        `/work-items/${encodePath(issueId)}/properties/${encodePath(propertyId)}/`
      ),
      { body: { value } }
    );
  }

  listMilestones(workspace: string, projectId: string): Promise<PaginatedResponse<Milestone>> {
    return this.request("GET", this.projectPath(workspace, projectId, "/milestones/"), { query: { per_page: 100 } });
  }

  createMilestone(workspace: string, projectId: string, input: Record<string, unknown>): Promise<Milestone> {
    return this.request("POST", this.projectPath(workspace, projectId, "/milestones/"), { body: input });
  }

  listInitiatives(workspace: string): Promise<PaginatedResponse<Initiative>> {
    return this.request("GET", this.apiPath(workspace, "/initiatives/"), { query: { per_page: 100 } });
  }

  createInitiative(workspace: string, input: Record<string, unknown>): Promise<Initiative> {
    return this.request("POST", this.apiPath(workspace, "/initiatives/"), { body: input });
  }

  updateIssue(
    workspace: string,
    projectId: string,
    issueId: string,
    input: Record<string, unknown>
  ): Promise<WorkItem> {
    return this.request("PATCH", this.projectPath(workspace, projectId, `/work-items/${encodePath(issueId)}/`), {
      body: input,
    });
  }

  archiveIssue(workspace: string, projectId: string, issueId: string): Promise<void> {
    return this.request("DELETE", this.projectPath(workspace, projectId, `/work-items/${encodePath(issueId)}/`));
  }

  addIssueComment(
    workspace: string,
    projectId: string,
    issueId: string,
    input: Record<string, unknown>
  ): Promise<unknown> {
    return this.request(
      "POST",
      this.projectPath(workspace, projectId, `/work-items/${encodePath(issueId)}/comments/`),
      { body: input }
    );
  }

  getTestingCapabilities(workspace: string, projectId: string): Promise<TestingCapabilities> {
    return this.request("GET", this.testingPath(workspace, projectId, "/capabilities/")).then((payload) =>
      parsePlaneResponse(testingCapabilitiesSchema, payload, "getTestingCapabilities")
    );
  }

  getQualityOverview(workspace: string, projectId: string): Promise<Record<string, unknown>> {
    return this.request("GET", this.testingPath(workspace, projectId, "/overview/"));
  }

  getRequirementCoverage(workspace: string, projectId: string): Promise<Record<string, unknown>> {
    return this.request("GET", this.testingPath(workspace, projectId, "/requirement-coverage/"));
  }

  listFolders(workspace: string, projectId: string): Promise<TestFolder[]> {
    return this.request("GET", this.testingPath(workspace, projectId, "/folders/"));
  }

  getFolder(workspace: string, projectId: string, folderId: string): Promise<TestFolder> {
    return this.request("GET", this.testingPath(workspace, projectId, `/folders/${encodePath(folderId)}/`));
  }

  createFolder(
    workspace: string,
    projectId: string,
    input: { name: string; parent_id?: string | null; sort_order?: number }
  ): Promise<TestFolder> {
    return this.request("POST", this.testingPath(workspace, projectId, "/folders/"), { body: input });
  }

  updateFolder(
    workspace: string,
    projectId: string,
    folderId: string,
    input: Partial<{ name: string; parent_id: string | null; sort_order: number }>
  ): Promise<TestFolder> {
    return this.request("PATCH", this.testingPath(workspace, projectId, `/folders/${encodePath(folderId)}/`), {
      body: input,
    });
  }

  deleteFolder(workspace: string, projectId: string, folderId: string): Promise<void> {
    return this.request("DELETE", this.testingPath(workspace, projectId, `/folders/${encodePath(folderId)}/`));
  }

  listTestCases(
    workspace: string,
    projectId: string,
    query: RequestOptions["query"] = {}
  ): Promise<TestCase[] | PaginatedResponse<TestCase>> {
    return this.request("GET", this.testingPath(workspace, projectId, "/test-cases/"), { query });
  }

  getTestCase(workspace: string, projectId: string, caseId: string): Promise<TestCase> {
    return this.request("GET", this.testingPath(workspace, projectId, `/test-cases/${encodePath(caseId)}/`));
  }

  async resolveTestCase(workspace: string, projectId: string, reference: string): Promise<TestCase> {
    if (UUID_PATTERN.test(reference)) return this.getTestCase(workspace, projectId, reference);
    const sequence = Number(reference);
    if (!Number.isInteger(sequence) || sequence < 1) {
      throw new PlaneQAError({ kind: "validation", message: `Invalid test case reference: ${reference}.` });
    }
    const response = await this.listTestCases(workspace, projectId, { per_page: 200 });
    const cases = Array.isArray(response) ? response : response.results;
    const testCase = cases.find((item) => item.sequence === sequence);
    if (!testCase) {
      throw new PlaneQAError({ kind: "not_found", status: 404, message: `Test case ${reference} was not found.` });
    }
    return testCase;
  }

  createTestCase(workspace: string, projectId: string, input: Record<string, unknown>): Promise<TestCase> {
    return this.request("POST", this.testingPath(workspace, projectId, "/test-cases/"), { body: input });
  }

  updateTestCase(
    workspace: string,
    projectId: string,
    caseId: string,
    input: Record<string, unknown>
  ): Promise<TestCase> {
    return this.request("PATCH", this.testingPath(workspace, projectId, `/test-cases/${encodePath(caseId)}/`), {
      body: input,
    });
  }

  archiveTestCase(workspace: string, projectId: string, caseId: string): Promise<void> {
    return this.request("DELETE", this.testingPath(workspace, projectId, `/test-cases/${encodePath(caseId)}/`));
  }

  searchTesting(
    workspace: string,
    projectId: string,
    query = "",
    scope: TestingSearchScope = "all"
  ): Promise<TestingSearchResponse> {
    return this.request("GET", this.testingPath(workspace, projectId, "/search/"), {
      query: { query, scope },
    });
  }

  exportTesting(
    workspace: string,
    projectId: string,
    query: string,
    scope: TestingSearchScope,
    format: TestingExportFormat
  ): Promise<string | Uint8Array> {
    return this.request("GET", this.testingPath(workspace, projectId, "/export/"), {
      query: { query, scope, export_format: format },
      headers: {
        Accept:
          format === "csv"
            ? "text/csv"
            : format === "excel"
              ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              : "text/html",
      },
      responseType: format === "excel" ? "array_buffer" : undefined,
    });
  }

  listTestCaseAttachments(workspace: string, projectId: string, caseId: string): Promise<TestCaseAttachment[]> {
    return this.request(
      "GET",
      this.testingPath(workspace, projectId, `/test-cases/${encodePath(caseId)}/attachments/`)
    );
  }

  async uploadTestCaseAttachment(
    workspace: string,
    projectId: string,
    caseId: string,
    input: { name: string; type: string; content: Blob }
  ): Promise<TestCaseAttachment> {
    const path = this.testingPath(workspace, projectId, `/test-cases/${encodePath(caseId)}/attachments/`);
    const signed = await this.request<TestCaseAttachmentUploadResponse>("POST", path, {
      body: { name: input.name, type: input.type, size: input.content.size },
    });
    const form = new FormData();
    for (const [key, value] of Object.entries(signed.upload_data.fields)) form.append(key, value);
    form.append("file", input.content, input.name);
    const uploadResponse = await this.fetcher(signed.upload_data.url, {
      method: "POST",
      body: form,
      signal: AbortSignal.timeout(this.timeoutMs),
    });
    if (!uploadResponse.ok) {
      throw new PlaneQAError({
        kind: "network",
        status: uploadResponse.status,
        message: `Attachment storage upload failed with HTTP ${uploadResponse.status}.`,
        retryable: uploadResponse.status >= 500,
      });
    }
    await this.request("PATCH", `${path}${encodePath(signed.asset_id)}/`);
    return signed.attachment;
  }

  deleteTestCaseAttachment(workspace: string, projectId: string, caseId: string, attachmentId: string): Promise<void> {
    return this.request(
      "DELETE",
      this.testingPath(
        workspace,
        projectId,
        `/test-cases/${encodePath(caseId)}/attachments/${encodePath(attachmentId)}/`
      )
    );
  }

  getTestCaseVersion(workspace: string, projectId: string, caseId: string, version: number): Promise<TestCaseVersion> {
    return this.request(
      "GET",
      this.testingPath(workspace, projectId, `/test-cases/${encodePath(caseId)}/versions/${version}/`)
    );
  }

  listTestCaseLinks(workspace: string, projectId: string, caseId: string): Promise<TestCaseLink[]> {
    return this.request("GET", this.testingPath(workspace, projectId, `/test-cases/${encodePath(caseId)}/work-items/`));
  }

  linkTestCase(workspace: string, projectId: string, caseId: string, issueId: string): Promise<TestCaseLink> {
    return this.request(
      "POST",
      this.testingPath(workspace, projectId, `/test-cases/${encodePath(caseId)}/work-items/`),
      { body: { issue_id: issueId } }
    );
  }

  unlinkTestCase(workspace: string, projectId: string, caseId: string, issueId: string): Promise<void> {
    return this.request(
      "DELETE",
      this.testingPath(workspace, projectId, `/test-cases/${encodePath(caseId)}/work-items/${encodePath(issueId)}/`)
    );
  }

  listTestRuns(
    workspace: string,
    projectId: string,
    query: RequestOptions["query"] = {}
  ): Promise<TestRun[] | PaginatedResponse<TestRun>> {
    return this.request("GET", this.testingPath(workspace, projectId, "/test-runs/"), { query });
  }

  getTestRun(workspace: string, projectId: string, runId: string): Promise<TestRun> {
    return this.request("GET", this.testingPath(workspace, projectId, `/test-runs/${encodePath(runId)}/`));
  }

  createTestRun(workspace: string, projectId: string, input: Record<string, unknown>): Promise<TestRun> {
    return this.request("POST", this.testingPath(workspace, projectId, "/test-runs/"), { body: input });
  }

  recordTestResult(
    workspace: string,
    projectId: string,
    runId: string,
    runCaseId: string,
    input: Record<string, unknown>
  ): Promise<TestResult> {
    return this.request(
      "POST",
      this.testingPath(workspace, projectId, `/test-runs/${encodePath(runId)}/cases/${encodePath(runCaseId)}/results/`),
      { body: input }
    );
  }

  createDefect(
    workspace: string,
    projectId: string,
    runId: string,
    runCaseId: string,
    resultId: string,
    input: Record<string, unknown> = {}
  ): Promise<WorkItem> {
    return this.request(
      "POST",
      this.testingPath(
        workspace,
        projectId,
        `/test-runs/${encodePath(runId)}/cases/${encodePath(runCaseId)}/results/${encodePath(resultId)}/defects/`
      ),
      { body: input }
    );
  }

  closeTestRun(workspace: string, projectId: string, runId: string): Promise<TestRun> {
    return this.request("POST", this.testingPath(workspace, projectId, `/test-runs/${encodePath(runId)}/close/`), {
      body: {},
    });
  }

  ingestAutomation(
    workspace: string,
    projectId: string,
    idempotencyKey: string,
    input: JsonObject
  ): Promise<Record<string, unknown>> {
    return this.request("POST", this.testingPath(workspace, projectId, "/automation-ingestions/"), {
      body: input,
      headers: { "Idempotency-Key": idempotencyKey },
      idempotent: true,
    });
  }
}
