/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import type { TTestCase, TTestRunInput } from "@plane/types";

type Props = {
  testCases: TTestCase[];
  onCancel: () => void;
  onCreate: (input: TTestRunInput) => Promise<void>;
};

export function TestRunBuilder({ testCases, onCancel, onCreate }: Props) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [build, setBuild] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  const toggleCase = (id: string) => {
    setSelectedIds((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  };

  const submit = async () => {
    if (!name.trim() || selectedIds.length === 0) return;
    setSaving(true);
    try {
      await onCreate({ name: name.trim(), build: build.trim(), test_case_ids: selectedIds });
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="rounded-lg border border-subtle bg-surface-1 p-5">
      <div className="mb-4">
        <h2 className="text-16 font-semibold text-primary">{t("testing.runs.builder_heading")}</h2>
        <p className="mt-1 text-13 text-secondary">{t("testing.runs.builder_hint")}</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="text-13 font-medium text-primary">
          {t("testing.runs.name_label")}
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="mt-2 h-10 w-full rounded-md border border-subtle bg-surface-1 px-3 text-14 outline-none focus:border-accent-strong"
            placeholder="Release 1.0 smoke"
          />
        </label>
        <label className="text-13 font-medium text-primary">
          {t("testing.runs.build_label")}
          <input
            value={build}
            onChange={(event) => setBuild(event.target.value)}
            className="mt-2 h-10 w-full rounded-md border border-subtle bg-surface-1 px-3 text-14 outline-none focus:border-accent-strong"
            placeholder="1.0.0+42"
          />
        </label>
      </div>
      <fieldset className="mt-5">
        <legend className="text-13 font-medium text-primary">{t("testing.runs.cases_label")}</legend>
        <div className="mt-2 max-h-72 overflow-y-auto rounded-md border border-subtle">
          {testCases.map((testCase) => (
            <label
              key={testCase.id}
              className="flex cursor-pointer items-center gap-3 border-b border-subtle px-3 py-2.5 last:border-b-0 hover:bg-surface-2"
            >
              <input
                type="checkbox"
                checked={selectedIds.includes(testCase.id)}
                onChange={() => toggleCase(testCase.id)}
                className="size-4"
              />
              <span className="w-16 text-12 font-medium text-secondary">TC-{testCase.sequence}</span>
              <span className="text-13 text-primary">{testCase.current.title}</span>
              <span className="ml-auto text-11 text-tertiary">v{testCase.current_version}</span>
            </label>
          ))}
          {testCases.length === 0 && <p className="p-4 text-13 text-secondary">{t("testing.runs.no_cases")}</p>}
        </div>
      </fieldset>
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="secondary" onClick={onCancel} disabled={saving}>
          {t("testing.cases.cancel")}
        </Button>
        <Button
          variant="primary"
          onClick={() => void submit()}
          disabled={saving || !name.trim() || !selectedIds.length}
        >
          {saving ? t("testing.runs.creating") : t("testing.runs.create_count", { count: selectedIds.length })}
        </Button>
      </div>
    </section>
  );
}
