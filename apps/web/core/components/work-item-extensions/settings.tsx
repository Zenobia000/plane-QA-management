/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { useMemo, useState } from "react";
import { Check, Pencil, Plus, Trash2 } from "lucide-react";
import type { TWorkItemProperty, TWorkItemPropertyKind } from "@plane/types";
import { CustomSelect } from "@plane/ui";
import { WorkItemTypeBadge } from "./type-badge";
import {
  useProjectWorkItemTypes,
  useWorkItemPropertyDefinitions,
  useWorkspaceWorkItemTypes,
  workItemExtensionService,
} from "@/hooks/use-work-item-extensions";

type Props = { workspaceSlug: string; projectId: string };

const fieldClass =
  "h-9 rounded border border-subtle bg-surface-1 px-2 text-12 text-primary outline-none focus:border-accent-strong";
const buttonClass =
  "inline-flex h-8 items-center justify-center gap-1.5 rounded px-3 text-12 font-medium disabled:cursor-not-allowed disabled:opacity-50";
const selectButtonClass = `${fieldClass} w-full justify-between font-normal`;

const propertyKindLabels: Record<TWorkItemPropertyKind, string> = {
  text: "Text",
  number: "Number",
  date: "Date",
  boolean: "Boolean",
  url: "URL",
  select: "Select",
  multi_select: "Multi select",
};

const propertyKinds = Object.keys(propertyKindLabels) as TWorkItemPropertyKind[];

const errorMessage = (error: unknown) => {
  if (error && typeof error === "object" && "error" in error) return String(error.error);
  return "The change could not be saved.";
};

export const parsePropertyOptions = (rawOptions: string) => {
  const usedValues = new Set<string>();

  return rawOptions
    .split(",")
    .map((label) => label.trim())
    .filter(Boolean)
    .map((label, index) => {
      const baseValue =
        label
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "_")
          .replace(/^_|_$/g, "") || `option_${index + 1}`;
      let value = baseValue;
      let suffix = 2;
      while (usedValues.has(value)) value = `${baseValue}_${suffix++}`;
      usedValues.add(value);

      return { label, value, sort_order: (index + 1) * 10 };
    });
};

export function WorkItemExtensionSettings({ workspaceSlug, projectId }: Props) {
  const { data: workspaceTypes, mutate: mutateWorkspaceTypes } = useWorkspaceWorkItemTypes(workspaceSlug);
  const { data: projectTypes, mutate: mutateProjectTypes } = useProjectWorkItemTypes(workspaceSlug, projectId);
  const { data: properties, mutate: mutateProperties } = useWorkItemPropertyDefinitions(workspaceSlug, projectId);
  const [typeName, setTypeName] = useState("");
  const [typeDescription, setTypeDescription] = useState("");
  const [typeLevel, setTypeLevel] = useState(0);
  const [typeIsEpic, setTypeIsEpic] = useState(false);
  const [typeToEnable, setTypeToEnable] = useState("");
  const [propertyId, setPropertyId] = useState<string | null>(null);
  const [propertyName, setPropertyName] = useState("");
  const [propertyDescription, setPropertyDescription] = useState("");
  const [propertyKind, setPropertyKind] = useState<TWorkItemPropertyKind>("text");
  const [propertyRequired, setPropertyRequired] = useState(false);
  const [propertyOptions, setPropertyOptions] = useState("");
  // null means the property applies to every type, which stays the default.
  const [propertyType, setPropertyType] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const enabledTypeIds = useMemo(() => new Set((projectTypes ?? []).map((item) => item.type.id)), [projectTypes]);
  const availableTypes = (workspaceTypes ?? []).filter((item) => item.is_active && !enabledTypeIds.has(item.id));

  const refreshTypes = async () => {
    await Promise.all([mutateWorkspaceTypes(), mutateProjectTypes()]);
  };

  const createType = async () => {
    if (!typeName.trim()) return;
    setBusy(true);
    setError("");
    try {
      const created = await workItemExtensionService.createWorkspaceType(workspaceSlug, {
        name: typeName.trim(),
        description: typeDescription.trim(),
        level: typeLevel,
        is_epic: typeIsEpic,
        is_active: true,
      });
      await workItemExtensionService.enableProjectType(workspaceSlug, projectId, {
        type_id: created.id,
        level: Math.max(0, Math.round(typeLevel)),
        is_default: !projectTypes?.length,
      });
      setTypeName("");
      setTypeDescription("");
      setTypeLevel(0);
      setTypeIsEpic(false);
      await refreshTypes();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  const enableType = async () => {
    if (!typeToEnable) return;
    setBusy(true);
    setError("");
    try {
      const definition = availableTypes.find((item) => item.id === typeToEnable);
      await workItemExtensionService.enableProjectType(workspaceSlug, projectId, {
        type_id: typeToEnable,
        level: Math.max(0, Math.round(definition?.level ?? 0)),
        is_default: !projectTypes?.length,
      });
      setTypeToEnable("");
      await mutateProjectTypes();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  const resetPropertyForm = () => {
    setPropertyId(null);
    setPropertyName("");
    setPropertyDescription("");
    setPropertyKind("text");
    setPropertyRequired(false);
    setPropertyOptions("");
    setPropertyType(null);
  };

  const editProperty = (definition: TWorkItemProperty) => {
    setPropertyId(definition.id);
    setPropertyName(definition.name);
    setPropertyDescription(definition.description);
    setPropertyKind(definition.kind);
    setPropertyRequired(definition.is_required);
    setPropertyOptions(definition.options.map((item) => item.label).join(", "));
    setPropertyType(definition.type);
  };

  const saveProperty = async () => {
    if (!propertyName.trim()) return;
    setBusy(true);
    setError("");
    const options = parsePropertyOptions(propertyOptions);
    const payload: Partial<TWorkItemProperty> = {
      name: propertyName.trim(),
      description: propertyDescription.trim(),
      kind: propertyKind,
      is_required: propertyRequired,
      is_active: true,
      type: propertyType,
      options: propertyKind === "select" || propertyKind === "multi_select" ? options : [],
    };
    try {
      if (propertyId) await workItemExtensionService.updateProperty(workspaceSlug, projectId, propertyId, payload);
      else await workItemExtensionService.createProperty(workspaceSlug, projectId, payload);
      resetPropertyForm();
      await mutateProperties();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-8 pb-10">
      {error && (
        <div className="rounded border border-danger-subtle bg-danger-subtle p-3 text-12 text-danger-primary">
          {error}
        </div>
      )}

      <section className="rounded-lg border border-subtle bg-surface-1">
        <div className="border-b border-subtle p-5">
          <h2 className="text-16 font-semibold text-primary">Work item types</h2>
          <p className="mt-1 text-12 text-secondary">
            Define the hierarchy and choose which types this project can use. New definitions are shared across this
            workspace.
          </p>
        </div>
        <div className="space-y-3 p-5">
          {projectTypes?.map((item) => (
            <div
              key={item.id}
              className="grid grid-cols-[minmax(0,1fr)_6rem_auto_auto] items-center gap-3 rounded border border-subtle p-3"
            >
              <span className="min-w-0">
                <WorkItemTypeBadge type={item.type} />
                {item.type.description && <span className="ml-2 text-11 text-tertiary">{item.type.description}</span>}
              </span>
              <label className="text-10 text-tertiary">
                Level
                <input
                  className={`${fieldClass} mt-1 w-full`}
                  type="number"
                  min={0}
                  defaultValue={item.level}
                  disabled={busy}
                  onBlur={(event) => {
                    const level = Number(event.target.value);
                    if (level !== item.level)
                      void workItemExtensionService
                        .updateProjectType(workspaceSlug, projectId, item.id, { level })
                        .then(() => mutateProjectTypes())
                        .catch((caught) => setError(errorMessage(caught)));
                  }}
                />
              </label>
              <button
                type="button"
                className={`${buttonClass} ${item.is_default ? "bg-success-subtle text-success-primary" : "bg-layer-2 text-secondary"}`}
                disabled={busy || item.is_default}
                onClick={() =>
                  void workItemExtensionService
                    .updateProjectType(workspaceSlug, projectId, item.id, { is_default: true })
                    .then(() => mutateProjectTypes())
                    .catch((caught) => setError(errorMessage(caught)))
                }
              >
                <Check className="size-3.5" /> {item.is_default ? "Default" : "Set default"}
              </button>
              <button
                type="button"
                className={`${buttonClass} bg-danger-subtle text-danger-primary`}
                disabled={busy || item.is_default}
                onClick={() => {
                  if (!window.confirm(`Disable ${item.type.name} for this project?`)) return;
                  void workItemExtensionService
                    .disableProjectType(workspaceSlug, projectId, item.id)
                    .then(() => mutateProjectTypes())
                    .catch((caught) => setError(errorMessage(caught)));
                }}
              >
                Disable
              </button>
            </div>
          ))}
          {!projectTypes?.length && <p className="text-12 text-tertiary">No work item types are enabled.</p>}

          {availableTypes.length > 0 && (
            <div className="flex gap-2 border-t border-subtle pt-4">
              <CustomSelect
                className="min-w-56"
                value={typeToEnable}
                label={
                  <span className="truncate">
                    {availableTypes.find((item) => item.id === typeToEnable)?.name ?? "Choose a workspace type"}
                  </span>
                }
                onChange={(value: string) => setTypeToEnable(value)}
                buttonClassName={selectButtonClass}
                maxHeight="lg"
              >
                {availableTypes.map((item) => (
                  <CustomSelect.Option key={item.id} value={item.id}>
                    {item.name}
                  </CustomSelect.Option>
                ))}
              </CustomSelect>
              <button
                type="button"
                className={`${buttonClass} bg-accent-primary text-on-color`}
                disabled={busy || !typeToEnable}
                onClick={() => void enableType()}
              >
                Enable type
              </button>
            </div>
          )}

          <div className="grid grid-cols-[1fr_1fr_6rem_auto_auto] gap-2 border-t border-subtle pt-4">
            <input
              className={fieldClass}
              value={typeName}
              onChange={(event) => setTypeName(event.target.value)}
              placeholder="New type name"
            />
            <input
              className={fieldClass}
              value={typeDescription}
              onChange={(event) => setTypeDescription(event.target.value)}
              placeholder="Description"
            />
            <input
              className={fieldClass}
              type="number"
              min={0}
              value={typeLevel}
              onChange={(event) => setTypeLevel(Number(event.target.value))}
              aria-label="Hierarchy level"
            />
            <label className="flex items-center gap-2 text-12 text-secondary">
              <input type="checkbox" checked={typeIsEpic} onChange={(event) => setTypeIsEpic(event.target.checked)} />{" "}
              Epic
            </label>
            <button
              type="button"
              className={`${buttonClass} bg-accent-primary text-on-color`}
              disabled={busy || !typeName.trim()}
              onClick={() => void createType()}
            >
              <Plus className="size-3.5" /> Create
            </button>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-subtle bg-surface-1">
        <div className="border-b border-subtle p-5">
          <h2 className="text-16 font-semibold text-primary">Custom properties</h2>
          <p className="mt-1 text-12 text-secondary">
            Add structured project fields that QA and delivery teams can edit on every work item.
          </p>
        </div>
        <div className="space-y-3 p-5">
          {properties?.map((definition) => (
            <div key={definition.id} className="flex items-center gap-3 rounded border border-subtle p-3">
              <span className="min-w-0 flex-1">
                <span className="font-medium text-primary">{definition.name}</span>
                <span className="ml-2 rounded bg-layer-2 px-1.5 py-0.5 text-10 text-secondary">
                  {propertyKindLabels[definition.kind] ?? definition.kind}
                </span>
                {definition.type && (
                  <span className="ml-2 text-10 text-tertiary">
                    {projectTypes?.find((item) => item.type.id === definition.type)?.type.name ?? "One type"} only
                  </span>
                )}
                {definition.is_required && <span className="ml-2 text-10 text-danger-primary">Required</span>}
                {!definition.is_active && <span className="ml-2 text-10 text-tertiary">Inactive</span>}
                {definition.description && (
                  <p className="mt-1 truncate text-11 text-tertiary">{definition.description}</p>
                )}
              </span>
              <button
                type="button"
                className={`${buttonClass} bg-layer-2 text-secondary`}
                onClick={() => editProperty(definition)}
              >
                <Pencil className="size-3.5" /> Edit
              </button>
              <button
                type="button"
                className={`${buttonClass} bg-layer-2 text-secondary`}
                onClick={() =>
                  void workItemExtensionService
                    .updateProperty(workspaceSlug, projectId, definition.id, { is_active: !definition.is_active })
                    .then(() => mutateProperties())
                    .catch((caught) => setError(errorMessage(caught)))
                }
              >
                {definition.is_active ? "Deactivate" : "Activate"}
              </button>
              <button
                type="button"
                className={`${buttonClass} bg-danger-subtle text-danger-primary`}
                onClick={() => {
                  if (!window.confirm(`Delete custom property ${definition.name}?`)) return;
                  void workItemExtensionService
                    .deleteProperty(workspaceSlug, projectId, definition.id)
                    .then(() => mutateProperties())
                    .catch((caught) => setError(errorMessage(caught)));
                }}
              >
                <Trash2 className="size-3.5" /> Delete
              </button>
            </div>
          ))}
          {!properties?.length && <p className="text-12 text-tertiary">No custom properties have been created.</p>}

          <div className="space-y-3 border-t border-subtle pt-4">
            <div className="grid grid-cols-2 gap-2">
              <input
                className={fieldClass}
                value={propertyName}
                onChange={(event) => setPropertyName(event.target.value)}
                placeholder="Property name"
              />
              <input
                className={fieldClass}
                value={propertyDescription}
                onChange={(event) => setPropertyDescription(event.target.value)}
                placeholder="Description"
              />
              <CustomSelect
                className="w-full"
                value={propertyKind}
                label={<span className="truncate">{propertyKindLabels[propertyKind]}</span>}
                onChange={(value: TWorkItemPropertyKind) => setPropertyKind(value)}
                buttonClassName={selectButtonClass}
                maxHeight="lg"
              >
                {propertyKinds.map((kind) => (
                  <CustomSelect.Option key={kind} value={kind}>
                    {propertyKindLabels[kind]}
                  </CustomSelect.Option>
                ))}
              </CustomSelect>
              {/* Scope. "All types" is the default and what every property was before this
                  existed; picking a type narrows who is asked for the value. */}
              <CustomSelect
                className="w-full"
                value={propertyType}
                label={
                  <span className="truncate">
                    {propertyType
                      ? (projectTypes?.find((item) => item.type.id === propertyType)?.type.name ?? "All types")
                      : "All types"}
                  </span>
                }
                onChange={(value: string | null) => setPropertyType(value)}
                buttonClassName={selectButtonClass}
                maxHeight="lg"
              >
                <CustomSelect.Option value={null}>All types</CustomSelect.Option>
                {(projectTypes ?? []).map((item) => (
                  <CustomSelect.Option key={item.type.id} value={item.type.id}>
                    {item.type.name}
                  </CustomSelect.Option>
                ))}
              </CustomSelect>
              {(propertyKind === "select" || propertyKind === "multi_select") && (
                <input
                  className={fieldClass}
                  value={propertyOptions}
                  onChange={(event) => setPropertyOptions(event.target.value)}
                  placeholder="Options, separated by commas"
                />
              )}
            </div>
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-12 text-secondary">
                <input
                  type="checkbox"
                  checked={propertyRequired}
                  onChange={(event) => setPropertyRequired(event.target.checked)}
                />{" "}
                Required
              </label>
              <div className="flex gap-2">
                {propertyId && (
                  <button
                    type="button"
                    className={`${buttonClass} bg-layer-2 text-secondary`}
                    onClick={resetPropertyForm}
                  >
                    Cancel
                  </button>
                )}
                <button
                  type="button"
                  className={`${buttonClass} bg-accent-primary text-on-color`}
                  disabled={busy || !propertyName.trim()}
                  onClick={() => void saveProperty()}
                >
                  {propertyId ? "Save property" : "Add property"}
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
