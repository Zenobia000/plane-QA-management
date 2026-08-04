/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { useMemo, useState } from "react";
import { Check, Pencil, Plus, Trash2 } from "lucide-react";
import { EmojiIconPickerTypes, EmojiPicker, Logo } from "@plane/propel/emoji-icon-picker";
import type { TLogoProps, TWorkItemProperty, TWorkItemPropertyKind } from "@plane/types";
import { CustomSelect } from "@plane/ui";
import { WorkItemTypeBadge, asLogo } from "./type-badge";
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

/**
 * Normalise what the picker hands back into the shape `logo_props` stores.
 *
 * The emoji tab yields a value to wrap; the icon tab yields the whole `{name, color}`
 * object already. Same conversion the project form does -- kept here rather than shared
 * because the picker's own callback is typed `any` and each caller narrows it locally.
 */
function toLogoProps(value: { type?: string; value?: unknown } | null): TLogoProps | Record<string, never> {
  if (!value?.type) return {};
  const payload = value.type === "emoji" ? { value: value.value } : value.value;
  return { in_use: value.type, [value.type]: payload } as TLogoProps;
}

export function WorkItemExtensionSettings({ workspaceSlug, projectId }: Props) {
  const { data: workspaceTypes, mutate: mutateWorkspaceTypes } = useWorkspaceWorkItemTypes(workspaceSlug);
  const { data: projectTypes, mutate: mutateProjectTypes } = useProjectWorkItemTypes(workspaceSlug, projectId);
  const { data: properties, mutate: mutateProperties } = useWorkItemPropertyDefinitions(workspaceSlug, projectId);
  const [typeName, setTypeName] = useState("");
  const [typeDescription, setTypeDescription] = useState("");
  const [typeLevel, setTypeLevel] = useState(0);
  const [typeIsEpic, setTypeIsEpic] = useState(false);
  // `{}` means "no logo chosen", which is what the model stores until someone picks one.
  const [typeLogo, setTypeLogo] = useState<TLogoProps | Record<string, never>>({});
  const [logoPickerOpen, setLogoPickerOpen] = useState(false);
  // The id of the type whose logo is being changed, or null when none is.
  const [editingLogoFor, setEditingLogoFor] = useState<string | null>(null);
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
        logo_props: typeLogo,
      });
      await workItemExtensionService.enableProjectType(workspaceSlug, projectId, {
        type_id: created.id,
        level: Math.max(0, Math.round(typeLevel)),
        is_default: !projectTypes?.length,
      });
      setTypeName("");
      setTypeLogo({});
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

  /**
   * Change one type's logo.
   *
   * `updateWorkspaceType` has existed on the service since types were added and had no
   * callers -- there was no edit path for a type at all. This gives it one for the field
   * that is purely presentational and therefore safe to change after the fact.
   */
  const setTypeLogoFor = async (typeId: string, logo: TLogoProps | Record<string, never>) => {
    setLogoPickerOpen(false);
    setEditingLogoFor(null);
    setError("");
    try {
      await workItemExtensionService.updateWorkspaceType(workspaceSlug, typeId, { logo_props: logo });
      await refreshTypes();
    } catch (caught) {
      setError(errorMessage(caught));
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

  /**
   * Move the overview's grouping to this property, or turn it off.
   *
   * The unique constraint is per project, so the outgoing holder is cleared before the
   * incoming one is set. Doing it the other way round fails on the database and surfaces
   * as a button that appears to do nothing.
   */
  const setGroupingDimension = async (definition: TWorkItemProperty) => {
    const next = !definition.is_grouping_dimension;
    try {
      if (next) {
        const current = properties?.find((item) => item.is_grouping_dimension && item.id !== definition.id);
        if (current)
          await workItemExtensionService.updateProperty(workspaceSlug, projectId, current.id, {
            is_grouping_dimension: false,
          });
      }
      await workItemExtensionService.updateProperty(workspaceSlug, projectId, definition.id, {
        is_grouping_dimension: next,
      });
      await mutateProperties();
    } catch (caught) {
      setError(errorMessage(caught));
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
              className="grid grid-cols-[auto_minmax(0,1fr)_6rem_auto_auto_auto] items-center gap-3 rounded border border-subtle p-3"
            >
              {/* The only way to change a type's appearance after creation. Everything else
                  about a type is still fixed once created, which is a separate gap. */}
              <EmojiPicker
                iconType="material"
                closeOnSelect={false}
                isOpen={logoPickerOpen && editingLogoFor === item.type.id}
                handleToggle={(open: boolean) => {
                  setEditingLogoFor(open ? item.type.id : null);
                  setLogoPickerOpen(open);
                }}
                className="flex items-center justify-center"
                buttonClassName="flex h-8 w-8 shrink-0 items-center justify-center rounded border border-subtle bg-surface-1"
                label={<Logo logo={asLogo(item.type.logo_props)} size={16} />}
                // TODO: fix types -- the picker's own callback is untyped
                onChange={(value: any) => void setTypeLogoFor(item.type.id, toLogoProps(value))}
                defaultIconColor={
                  "in_use" in item.type.logo_props && item.type.logo_props.in_use === "icon"
                    ? item.type.logo_props.icon?.color
                    : undefined
                }
                defaultOpen={
                  "in_use" in item.type.logo_props && item.type.logo_props.in_use === "emoji"
                    ? EmojiIconPickerTypes.EMOJI
                    : EmojiIconPickerTypes.ICON
                }
              />
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
              {/* Whether the coverage report asks this type for an acceptance test. Off for
                  work that describes how something is built rather than what it must do --
                  counting those buried the one real gap under seven that were not. Stored on
                  the workspace type, so it applies wherever the type is enabled. */}
              <button
                type="button"
                title={
                  item.type.needs_acceptance
                    ? "Counted by requirement coverage. Click to exclude."
                    : "Not counted by requirement coverage. Click to include."
                }
                className={`${buttonClass} ${item.type.needs_acceptance ? "bg-layer-2 text-secondary" : "bg-layer-2 text-tertiary"}`}
                disabled={busy}
                onClick={() =>
                  void workItemExtensionService
                    .updateWorkspaceType(workspaceSlug, item.type.id, {
                      needs_acceptance: !item.type.needs_acceptance,
                    })
                    .then(() => mutateProjectTypes())
                    .catch((caught) => setError(errorMessage(caught)))
                }
              >
                {item.type.needs_acceptance ? "Needs tests" : "No tests needed"}
              </button>
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

          <div className="grid grid-cols-[auto_1fr_1fr_6rem_auto_auto] gap-2 border-t border-subtle pt-4">
            <EmojiPicker
              iconType="material"
              closeOnSelect={false}
              isOpen={logoPickerOpen && editingLogoFor === null}
              handleToggle={(open: boolean) => {
                setEditingLogoFor(null);
                setLogoPickerOpen(open);
              }}
              className="flex items-center justify-center"
              buttonClassName="flex h-9 w-9 shrink-0 items-center justify-center rounded border border-subtle bg-surface-1"
              label={<Logo logo={asLogo(typeLogo)} size={16} />}
              // TODO: fix types -- the picker's own callback is untyped
              onChange={(value: any) => {
                setTypeLogo(toLogoProps(value));
                setLogoPickerOpen(false);
              }}
              defaultIconColor={"in_use" in typeLogo && typeLogo.in_use === "icon" ? typeLogo.icon?.color : undefined}
              defaultOpen={
                "in_use" in typeLogo && typeLogo.in_use === "emoji"
                  ? EmojiIconPickerTypes.EMOJI
                  : EmojiIconPickerTypes.ICON
              }
            />
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
                {definition.is_grouping_dimension && (
                  <span className="ml-2 rounded bg-accent-subtle px-1.5 py-0.5 text-10 text-accent-primary">
                    Overview grouping
                  </span>
                )}
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
              {/* What the project overview groups its intake panel by. Offered only on
                  select-like properties: grouping by free text produces one bucket per
                  typo, which is the server's rule too and not a UI preference.

                  Clearing the previous holder first, because the database allows one per
                  project -- sending the new one straight in would fail the constraint and
                  read to the user as "the button does nothing". */}
              {(definition.kind === "select" || definition.kind === "multi_select") && (
                <button
                  type="button"
                  className={`${buttonClass} bg-layer-2 text-secondary`}
                  onClick={() => void setGroupingDimension(definition)}
                >
                  {definition.is_grouping_dimension ? "Stop grouping by this" : "Group overview by this"}
                </button>
              )}
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
