/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useTranslation } from "@plane/i18n";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TIssuePriorities, TPortfolioStatus, TProject } from "@plane/types";

const STATES: { value: TPortfolioStatus; label: string }[] = [
  { value: "planned", label: "Planned" },
  { value: "in_progress", label: "In progress" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
];

const PRIORITIES: { value: TIssuePriorities; label: string }[] = [
  { value: "urgent", label: "Urgent" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
  { value: "none", label: "None" },
];

const fieldClass =
  "h-8 w-full rounded border border-subtle bg-surface-1 px-2 text-12 text-primary outline-none focus:border-accent-strong disabled:opacity-60";

type Props = {
  project: TProject;
  disabled: boolean;
  onChange: (changes: Partial<TProject>) => Promise<void>;
};

/**
 * The properties panel.
 *
 * `state` uses the portfolio vocabulary that milestones and initiatives already speak, and
 * `priority` the work-item scale, rather than either inventing words that mean the same
 * thing one level up. Each control writes on change: there is no form to submit because
 * there is nothing here that is only valid in combination with something else.
 */
export function PropertiesPanel({ project, disabled, onChange }: Props) {
  const { t } = useTranslation();

  /**
   * Every control here fired its write as a floating promise, so a rejected save was an
   * unhandled rejection: no message, and the select left showing a value the server never
   * accepted. Reporting the failure is what tells the reader the field did not stick.
   */
  const save = (changes: Partial<TProject>) => {
    onChange(changes).catch(() => {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("project_overview.properties.not_saved_title"),
        message: t("project_overview.properties.not_saved_message"),
      });
    });
  };

  return (
    <section className="rounded border border-subtle p-4">
      <h2 className="text-13 font-medium text-primary">{t("project_overview.properties.title")}</h2>
      <dl className="mt-3 space-y-3">
        <div>
          <dt className="mb-1 text-11 text-tertiary">{t("project_overview.properties.state")}</dt>
          <dd>
            <select
              aria-label={t("project_overview.properties.state_label")}
              className={fieldClass}
              value={project.state ?? ""}
              disabled={disabled}
              onChange={(event) => save({ state: (event.target.value || null) as TPortfolioStatus | null })}
            >
              <option value="">{t("project_overview.properties.not_set")}</option>
              {STATES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </dd>
        </div>

        <div>
          <dt className="mb-1 text-11 text-tertiary">{t("project_overview.properties.priority")}</dt>
          <dd>
            <select
              aria-label={t("project_overview.properties.priority_label")}
              className={fieldClass}
              value={project.priority ?? "none"}
              disabled={disabled}
              onChange={(event) => save({ priority: event.target.value as TIssuePriorities })}
            >
              {PRIORITIES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </dd>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <dt className="mb-1 text-11 text-tertiary">{t("project_overview.properties.start")}</dt>
            <dd>
              <input
                type="date"
                aria-label={t("project_overview.properties.start_label")}
                className={fieldClass}
                value={project.start_date ?? ""}
                disabled={disabled}
                onChange={(event) => save({ start_date: event.target.value || null })}
              />
            </dd>
          </div>
          <div>
            <dt className="mb-1 text-11 text-tertiary">{t("project_overview.properties.target")}</dt>
            <dd>
              <input
                type="date"
                aria-label={t("project_overview.properties.target_label")}
                className={fieldClass}
                value={project.target_date ?? ""}
                disabled={disabled}
                onChange={(event) => save({ target_date: event.target.value || null })}
              />
            </dd>
          </div>
        </div>
      </dl>
    </section>
  );
}
