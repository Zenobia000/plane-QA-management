export type JsonPrimitive = boolean | number | string | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };

export interface PaginatedResponse<T> {
  results: T[];
  next_cursor?: string;
  prev_cursor?: string;
  total_count?: number;
  total_pages?: number;
}

export interface Project {
  id: string;
  name: string;
  identifier: string;
  workspace: string | { id: string; slug?: string };
  description?: string;
  created_at?: string;
  updated_at?: string;
  [key: string]: unknown;
}

export interface State {
  id: string;
  name: string;
  group: "backlog" | "unstarted" | "started" | "completed" | "cancelled" | string;
  color?: string;
  [key: string]: unknown;
}

/**
 * Whether a work item states a behaviour the system must have, a quality it must hold to,
 * or is not a requirement at all -- a task implements one and a bug reports one broken,
 * so neither *is* one.
 *
 * Crosses every level of the breakdown: an epic, a feature and a story can each carry any
 * of the three. That is why it sits beside the work item type rather than inside it -- the
 * backend keeps it on `Issue`, not `IssueType`, so that the number of types stays the depth
 * of the tree instead of depth × nature.
 *
 * Declared once here because the CLI and the MCP server both narrow user input against it;
 * two copies of a closed set drift the moment the backend adds a fourth.
 */
export const REQUIREMENT_KINDS = ["none", "functional", "quality"] as const;
export type RequirementKind = (typeof REQUIREMENT_KINDS)[number];

export interface WorkItem {
  id: string;
  name: string;
  sequence_id: number;
  project_id?: string;
  state_id?: string;
  priority?: string;
  description_html?: string;
  requirement_kind?: RequirementKind;
  created_at?: string;
  updated_at?: string;
  [key: string]: unknown;
}

export interface WorkItemType {
  id: string;
  name: string;
  description: string;
  is_epic: boolean;
  is_default: boolean;
  is_active: boolean;
  level: number;
  [key: string]: unknown;
}

export interface WorkItemPropertyOption {
  id: string;
  label: string;
  value: string;
  sort_order: number;
}

export interface WorkItemProperty {
  id: string;
  name: string;
  description: string;
  kind: "text" | "number" | "date" | "boolean" | "select" | "multi_select" | "url";
  is_required: boolean;
  is_active: boolean;
  sort_order: number;
  default_value: JsonValue | null;
  options: WorkItemPropertyOption[];
  [key: string]: unknown;
}

export interface Milestone {
  id: string;
  name: string;
  description: string;
  target_date: string | null;
  status: "planned" | "in_progress" | "completed" | "cancelled";
  sort_order: number;
  [key: string]: unknown;
}

export interface Initiative {
  id: string;
  name: string;
  description: string;
  target_date: string | null;
  status: "planned" | "in_progress" | "completed" | "cancelled";
  projects: Array<{ id: string; name: string; identifier: string }>;
  [key: string]: unknown;
}

export interface TestingCapabilities {
  enabled: boolean;
  stage: string;
  capabilities: {
    test_cases: boolean;
    test_runs: boolean;
    reports: boolean;
    automation_ingestion: boolean;
  };
}

/** A saved work-item query plus its presentation settings. */
export interface SavedView {
  id: string;
  name: string;
  description: string;
  /** Set this; the server compiles `query` from it. */
  filters: Record<string, unknown>;
  query: Record<string, unknown>;
  display_filters: Record<string, unknown>;
  display_properties: Record<string, unknown>;
  /** 0 private, 1 public. */
  access: number;
  is_locked: boolean;
  project: string | null;
  workspace: string;
  owned_by: string;
  created_at: string;
  updated_at: string;
}

export interface SavedViewInput {
  name: string;
  description?: string;
  filters?: Record<string, unknown>;
  display_filters?: Record<string, unknown>;
  display_properties?: Record<string, unknown>;
  access?: number;
  is_locked?: boolean;
}

export interface TestFolder {
  id: string;
  name: string;
  parent_id: string | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface TestStep {
  id?: string;
  position?: number;
  action: JsonValue;
  expected_result?: JsonValue;
}

export interface TestCaseVersion {
  id: string;
  version: number;
  title: string;
  description: JsonValue;
  preconditions: JsonValue;
  priority: string;
  tags: string[];
  steps: TestStep[];
  created_at: string;
  created_by_id?: string | null;
}

export interface TestCase {
  id: string;
  sequence: number;
  folder_id: string | null;
  current_version: number;
  archived_at: string | null;
  current: TestCaseVersion;
  work_item_ids: string[];
  latest_status: string | null;
}

export interface TestCaseLink {
  id: string;
  test_case_id: string;
  issue_id: string;
  created_at: string;
}

export interface TestCaseAttachment {
  id: string;
  attributes: { name: string; type: string; size: number };
  size: number;
  created_at: string;
  created_by_id: string | null;
  download_url: string;
  preview_url: string | null;
}

export type TestingSearchScope = "all" | "test_cases" | "work_items";
export type TestingExportFormat = "csv" | "html" | "excel";

export interface TestingSearchResult {
  kind: "test_case" | "work_item";
  id: string;
  identifier: string;
  sequence: number;
  title: string;
  description: string;
  preconditions: string;
  steps: string;
  priority: string;
  status: string;
  folder: string;
  tags: string[];
  linked_record_ids: string[];
  linked_records: string[];
  updated_at: string;
  state_group?: string | null;
  work_item_type?: string | null;
}

export interface TestingSearchResponse {
  query: string;
  scope: TestingSearchScope;
  count: number;
  results: TestingSearchResult[];
}

export interface TestCaseAttachmentUploadResponse {
  asset_id: string;
  asset_url: string;
  upload_data: { url: string; fields: Record<string, string> };
  attachment: TestCaseAttachment;
}

export interface TestResult {
  id: string;
  sequence: number;
  status: "passed" | "failed" | "blocked" | "skipped";
  actual_result: JsonValue;
  duration_ms?: number | null;
  created_at: string;
  defects: Array<{ id: string; name: string; sequence_id: number; state_group: string }>;
}

export interface TestRunCase {
  id: string;
  test_case_id: string;
  test_case_version: TestCaseVersion;
  position: number;
  latest_status: string;
  results: TestResult[];
}

export interface TestRun {
  id: string;
  name: string;
  status: "open" | "completed";
  run_type: string;
  build: string;
  configuration: JsonValue;
  run_cases: TestRunCase[];
  progress: Record<string, number>;
  [key: string]: unknown;
}

export interface PlaneQAClientOptions {
  baseUrl: string;
  apiKey: string;
  fetch?: typeof fetch;
  timeoutMs?: number;
  maxRetries?: number;
  retryBaseDelayMs?: number;
}

export interface RequestOptions {
  query?: Record<string, boolean | number | string | null | undefined>;
  body?: unknown;
  headers?: Record<string, string>;
  idempotent?: boolean;
  signal?: AbortSignal;
  responseType?: "array_buffer";
}
