/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import type { TTestCase, TTestFolder, TTestRunInput } from "@plane/types";
import { CycleService } from "@/services/cycle.service";
import { ModuleService } from "@/services/module.service";

type Props = {
  workspaceSlug: string;
  projectId: string;
  testCases: TTestCase[];
  folders: TTestFolder[];
  onCancel: () => void;
  onCreate: (input: TTestRunInput) => Promise<void>;
};

type Scope = { id: string; name: string };

const cycleService = new CycleService();
const moduleService = new ModuleService();

export function TestRunBuilder({ workspaceSlug, projectId, testCases, folders, onCancel, onCreate }: Props) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [build, setBuild] = useState("");
  const [query, setQuery] = useState("");
  const [cycleId, setCycleId] = useState("");
  const [moduleId, setModuleId] = useState("");
  const [cycles, setCycles] = useState<Scope[]>([]);
  const [modules, setModules] = useState<Scope[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  // A run that is not scoped to a sprint cannot be reported against one, which is
  // how sprint planning and test execution drifted apart: the API accepted a cycle
  // all along and the builder never offered it.
  useEffect(() => {
    let active = true;
    void (async () => {
      const [cycleList, moduleList] = await Promise.all([
        cycleService.getCyclesWithParams(workspaceSlug, projectId).catch(() => []),
        moduleService.getModules(workspaceSlug, projectId).catch(() => []),
      ]);
      if (!active) return;
      setCycles(cycleList.map((cycle) => ({ id: cycle.id, name: cycle.name })));
      setModules(moduleList.map((item) => ({ id: item.id, name: item.name })));
    })();
    return () => {
      active = false;
    };
  }, [projectId, workspaceSlug]);

  const suiteName = useMemo(() => {
    const byId = new Map(folders.map((folder) => [folder.id, folder.name]));
    return (folderId: string | null) => (folderId && byId.get(folderId)) || t("testing.runs.unfiled_suite");
  }, [folders, t]);

  // Grouping by suite and filtering by text is what removes the trip to the Test
  // cases tab: a flat, unsearchable list meant the only way to know what to pick
  // was to go and look somewhere else first.
  const grouped = useMemo(() => {
    const term = query.trim().toLowerCase();
    const matching = testCases.filter(
      (testCase) =>
        !term || testCase.current.title.toLowerCase().includes(term) || `tc-${testCase.sequence}`.includes(term)
    );
    const groups = new Map<string, TTestCase[]>();
    for (const testCase of matching) {
      const key = suiteName(testCase.folder_id);
      groups.set(key, [...(groups.get(key) ?? []), testCase]);
    }
    return [...groups.entries()].toSorted(([a], [b]) => a.localeCompare(b));
  }, [query, suiteName, testCases]);

  const visibleIds = grouped.flatMap(([, cases]) => cases.map((testCase) => testCase.id));

  const toggleCase = (id: string) =>
    setSelectedIds((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));

  const submit = async () => {
    if (!name.trim() || selectedIds.length === 0) return;
    setSaving(true);
    try {
      await onCreate({
        name: name.trim(),
        build: build.trim(),
        test_case_ids: selectedIds,
        cycle_id: cycleId || null,
        module_id: moduleId || null,
      });
    } finally {
      setSaving(false);
    }
  };

  const fieldClass =
    "mt-2 h-10 w-full rounded-md border border-subtle bg-surface-1 px-3 text-14 outline-none focus:border-accent-strong";

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
            className={fieldClass}
            placeholder="Release 1.0 smoke"
          />
        </label>
        <label className="text-13 font-medium text-primary">
          {t("testing.runs.build_label")}
          <input
            value={build}
            onChange={(event) => setBuild(event.target.value)}
            className={fieldClass}
            placeholder="1.0.0+42"
          />
        </label>
        <label className="text-13 font-medium text-primary">
          {t("testing.runs.cycle")}
          <select value={cycleId} onChange={(event) => setCycleId(event.target.value)} className={fieldClass}>
            <option value="">{t("testing.runs.no_scope")}</option>
            {cycles.map((cycle) => (
              <option key={cycle.id} value={cycle.id}>
                {cycle.name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-13 font-medium text-primary">
          {t("testing.runs.module")}
          <select value={moduleId} onChange={(event) => setModuleId(event.target.value)} className={fieldClass}>
            <option value="">{t("testing.runs.no_scope")}</option>
            {modules.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <fieldset className="mt-5">
        <div className="flex flex-wrap items-center gap-3">
          <legend className="text-13 font-medium text-primary">{t("testing.runs.cases_label")}</legend>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label={t("testing.runs.search")}
            placeholder={t("testing.runs.search_placeholder")}
            className="h-8 min-w-0 flex-1 rounded border border-subtle bg-surface-1 px-2 text-12 text-primary outline-none"
          />
          <button
            type="button"
            onClick={() => setSelectedIds((current) => [...new Set([...current, ...visibleIds])])}
            disabled={!visibleIds.length}
            className="text-12 font-medium text-accent-primary disabled:text-disabled"
          >
            {t("testing.runs.select_all", { count: visibleIds.length })}
          </button>
          <button
            type="button"
            onClick={() => setSelectedIds([])}
            disabled={!selectedIds.length}
            className="text-12 font-medium text-secondary disabled:text-disabled"
          >
            {t("testing.runs.clear")}
          </button>
        </div>
        <div className="mt-2 max-h-72 overflow-y-auto rounded-md border border-subtle">
          {grouped.map(([suite, cases]) => (
            <div key={suite}>
              <p className="sticky top-0 border-b border-subtle bg-surface-2 px-3 py-1.5 text-11 font-semibold text-secondary">
                {suite}
              </p>
              {cases.map((testCase) => (
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
                  <span className="min-w-0 flex-1 truncate text-13 text-primary">{testCase.current.title}</span>
                  <span className="text-11 text-tertiary">v{testCase.current_version}</span>
                </label>
              ))}
            </div>
          ))}
          {!testCases.length && <p className="p-4 text-13 text-secondary">{t("testing.runs.no_cases")}</p>}
          {!!testCases.length && !grouped.length && (
            <p className="p-4 text-13 text-secondary">{t("testing.runs.no_matches")}</p>
          )}
        </div>
      </fieldset>
      <div className="mt-5 flex items-center justify-end gap-3">
        <span className="text-12 text-secondary">
          {t("testing.runs.selected_count", { count: selectedIds.length })}
        </span>
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
