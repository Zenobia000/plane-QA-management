/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { ListTodo } from "lucide-react";
import { Logo } from "@plane/propel/emoji-icon-picker";
import type { TLogoProps, TWorkItemType } from "@plane/types";
import { cn } from "@plane/utils";

type Props = {
  type?: TWorkItemType;
  name?: string;
  compact?: boolean;
  className?: string;
};

/**
 * The stored value as something `Logo` will accept.
 *
 * `logo_props` is `{}` until someone picks one, and an empty object is not a logo -- it is
 * the absence of one, which every caller has to render as a fallback rather than pass on.
 */
export function asLogo(logo: TLogoProps | Record<string, never> | undefined): TLogoProps | undefined {
  return logo && "in_use" in logo && logo.in_use ? (logo as TLogoProps) : undefined;
}

/**
 * How a work item type appears everywhere it appears.
 *
 * This is the single render path for a type across the app, which is why the hardcoded
 * icon mattered: `IssueType.logo_props` has existed as long as the table has, the
 * serializer accepts it and the MCP server already writes it, yet every type still drew
 * the same grey checklist. Types nobody has given a logo keep that as the fallback.
 */
export function WorkItemTypeBadge({ type, name, compact = false, className }: Props) {
  const label = type?.name ?? name ?? "Work item";
  return (
    <span
      title={label}
      className={cn(
        "inline-flex min-w-0 items-center gap-1 rounded-sm bg-layer-2 px-1.5 py-0.5 text-caption-sm-medium text-secondary",
        type?.is_epic && "bg-accent-primary/10 text-accent-primary",
        className
      )}
    >
      {asLogo(type?.logo_props) ? (
        <span className="flex size-3.5 shrink-0 items-center justify-center">
          <Logo logo={asLogo(type?.logo_props)} size={14} />
        </span>
      ) : (
        <ListTodo className="size-3.5 shrink-0" />
      )}
      {!compact && <span className="truncate">{label}</span>}
    </span>
  );
}
