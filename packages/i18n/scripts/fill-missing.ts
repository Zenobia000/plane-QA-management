/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * Fill every locale's missing keys with the English string.
 *
 * sync-check fails a build when a locale lacks a key English has, so adding one
 * UI string otherwise means editing all nineteen locale files by hand. This
 * project maintains real translations for en and zh-TW only; the rest carry the
 * English string, which is what a user would see anyway once i18next fell back.
 * Writing that down as a copy rather than an absence keeps the fallback on the
 * path that is actually exercised — no locale in this repo has ever shipped a
 * missing namespace file.
 *
 * Existing values are never overwritten and key order is preserved, so a
 * translated locale only ever gains the lines it was missing.
 *
 *   tsx scripts/fill-missing.ts            # write
 *   tsx scripts/fill-missing.ts --check    # exit 1 if a write would change anything
 */

import fs from "node:fs";
import path from "node:path";

import { LOCALES_DIR, listLocales, readJsonFile } from "./lib/locale-io.js";

type Json = Record<string, unknown>;

const SOURCE_LOCALE = "en";

const isObject = (value: unknown): value is Json =>
  value !== null && typeof value === "object" && !Array.isArray(value);

const joinKey = (prefix: string, key: string) => (prefix ? `${prefix}.${key}` : key);

/**
 * Merge `source` into `target`, keeping every value and key position `target`
 * already has. Keys only `source` has are appended at their own nesting level,
 * and their paths are collected into `added`.
 */
function fill(source: Json, target: Json, prefix: string, added: string[]): Json {
  const merged: Json = {};

  for (const [key, value] of Object.entries(target)) {
    const sourceValue = source[key];
    merged[key] =
      isObject(value) && isObject(sourceValue) ? fill(sourceValue, value, joinKey(prefix, key), added) : value;
  }

  for (const [key, value] of Object.entries(source)) {
    if (key in merged) continue;
    if (isObject(value)) {
      merged[key] = fill(value, {}, joinKey(prefix, key), added);
    } else {
      merged[key] = value;
      added.push(joinKey(prefix, key));
    }
  }

  return merged;
}

const serialize = (data: Json) => `${JSON.stringify(data, null, 2)}\n`;

function main() {
  const checkMode = process.argv.includes("--check");
  const sourceDir = path.join(LOCALES_DIR, SOURCE_LOCALE);
  const namespaces = fs
    .readdirSync(sourceDir)
    .filter((file) => file.endsWith(".json"))
    .toSorted();

  let changed = 0;

  for (const locale of listLocales()) {
    if (locale === SOURCE_LOCALE) continue;

    for (const namespace of namespaces) {
      const sourceData = readJsonFile(path.join(sourceDir, namespace));
      const targetPath = path.join(LOCALES_DIR, locale, namespace);
      const exists = fs.existsSync(targetPath);
      const targetData = exists ? readJsonFile(targetPath) : {};

      const added: string[] = [];
      const merged = fill(sourceData, targetData, "", added);
      const next = serialize(merged);

      if (exists && next === fs.readFileSync(targetPath, "utf-8")) continue;

      changed += 1;
      const label = exists ? `${added.length} key(s)` : "new file";
      console.log(`  ${checkMode ? "would fill" : "filled"} ${locale}/${namespace} — ${label}`);
      if (!checkMode) {
        fs.mkdirSync(path.dirname(targetPath), { recursive: true });
        fs.writeFileSync(targetPath, next);
      }
    }
  }

  if (changed === 0) {
    console.log("All locales carry every English key.");
    return;
  }

  if (checkMode) {
    console.error(`\n${changed} file(s) are missing English keys. Run: pnpm --filter @plane/i18n fill`);
    process.exit(1);
  }
  console.log(`\nUpdated ${changed} file(s).`);
}

main();
