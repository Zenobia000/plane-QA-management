import { z } from "zod";

import { PlaneQAError } from "./errors";

export const projectSchema = z
  .object({
    id: z.string().uuid(),
    name: z.string().min(1),
    identifier: z.string().min(1),
    workspace: z.union([z.string(), z.object({ id: z.string(), slug: z.string().optional() }).passthrough()]),
  })
  .passthrough();

export const stateSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    group: z.string(),
  })
  .passthrough();

export const testingCapabilitiesSchema = z.object({
  enabled: z.boolean(),
  stage: z.string(),
  capabilities: z.object({
    test_cases: z.boolean(),
    test_runs: z.boolean(),
    reports: z.boolean(),
    automation_ingestion: z.boolean(),
  }),
});

export const testFolderSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  parent_id: z.string().uuid().nullable(),
  sort_order: z.number().int(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const testCaseVersionSchema = z.object({
  id: z.string().uuid(),
  version: z.number().int().positive(),
  title: z.string(),
  description: z.unknown(),
  preconditions: z.unknown(),
  priority: z.string(),
  tags: z.array(z.string()),
  steps: z.array(
    z.object({
      id: z.string().optional(),
      position: z.number().int().optional(),
      action: z.unknown(),
      expected_result: z.unknown().optional(),
    })
  ),
  created_at: z.string(),
  created_by_id: z.string().nullable().optional(),
});

export const testCaseSchema = z.object({
  id: z.string().uuid(),
  sequence: z.number().int().positive(),
  folder_id: z.string().uuid().nullable(),
  current_version: z.number().int().positive(),
  archived_at: z.string().nullable(),
  current: testCaseVersionSchema,
  work_item_ids: z.array(z.string().uuid()),
  latest_status: z.string().nullable(),
});

export const paginatedSchema = <T extends z.ZodTypeAny>(item: T) =>
  z
    .object({
      results: z.array(item),
      next_cursor: z.string().optional(),
      prev_cursor: z.string().optional(),
      total_count: z.number().int().optional(),
      total_pages: z.number().int().optional(),
    })
    .passthrough();

export const parsePlaneResponse = <T>(schema: z.ZodType<T>, payload: unknown, operation: string): T => {
  const parsed = schema.safeParse(payload);
  if (!parsed.success) {
    throw new PlaneQAError({
      kind: "server",
      message: `Invalid Plane response for ${operation}: ${parsed.error.issues[0]?.message ?? "schema mismatch"}`,
      details: parsed.error.flatten(),
    });
  }
  return parsed.data;
};
