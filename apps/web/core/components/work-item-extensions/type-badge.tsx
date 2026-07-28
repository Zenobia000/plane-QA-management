/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { ListTodo } from "lucide-react";
import type { TWorkItemType } from "@plane/types";
import { cn } from "@plane/utils";

type Props = {
  type?: TWorkItemType;
  name?: string;
  compact?: boolean;
  className?: string;
};

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
      <ListTodo className="size-3.5 shrink-0" />
      {!compact && <span className="truncate">{label}</span>}
    </span>
  );
}
