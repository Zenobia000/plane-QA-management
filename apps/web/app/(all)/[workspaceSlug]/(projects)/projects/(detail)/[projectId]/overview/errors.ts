/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * Pull something readable out of whatever the overview service threw.
 *
 * The service rethrows the raw DRF body rather than an Error, so a rejected write arrives
 * as `{url: ["Enter a valid URL."]}` or `{detail: "..."}`. Anything unrecognised falls back
 * to the caller's own wording -- an empty toast is worse than a generic one.
 */
export function readError(error: unknown, fallback: string): string {
  if (typeof error === "string") return error;
  if (error && typeof error === "object") {
    for (const value of Object.values(error as Record<string, unknown>)) {
      if (typeof value === "string") return value;
      if (Array.isArray(value) && typeof value[0] === "string") return value[0];
    }
  }
  return fallback;
}
