/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { Timer } from "lucide-react";
import { EnterpriseService } from "@plane/services";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";

const service = new EnterpriseService();

type TIssueActivityWorklogCreateButton = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  disabled: boolean;
};

/**
 * Log time against this work item.
 *
 * Hours and minutes rather than a decimal, matching how the estimate input takes them and
 * how the column stores them. The endpoint refuses a zero duration, so the button does too
 * rather than posting something it knows will fail.
 */
export function IssueActivityWorklogCreateButton({
  workspaceSlug,
  projectId,
  issueId,
  disabled,
}: TIssueActivityWorklogCreateButton) {
  const [open, setOpen] = useState(false);
  const [hours, setHours] = useState(0);
  const [minutes, setMinutes] = useState(0);
  const [busy, setBusy] = useState(false);

  const total = hours * 60 + minutes;

  const submit = async () => {
    if (!total) return;
    setBusy(true);
    try {
      await service.createWorklog(workspaceSlug, projectId, issueId, {
        duration: total,
        logged_at: new Date().toISOString().slice(0, 10),
      });
      setHours(0);
      setMinutes(0);
      setOpen(false);
      setToast({ type: TOAST_TYPE.SUCCESS, title: "Logged", message: "Time added to this work item." });
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: "Could not log the time." });
    } finally {
      setBusy(false);
    }
  };

  if (disabled) return <></>;

  return (
    <div className="flex items-center gap-2">
      {open ? (
        <>
          <input
            type="number"
            min={0}
            aria-label="Hours"
            className="h-7 w-14 rounded border border-subtle bg-surface-1 px-2 text-12 outline-none focus:border-accent-strong"
            value={hours}
            onChange={(event) => setHours(Math.max(0, Number(event.target.value)))}
          />
          <input
            type="number"
            min={0}
            max={59}
            aria-label="Minutes"
            className="h-7 w-14 rounded border border-subtle bg-surface-1 px-2 text-12 outline-none focus:border-accent-strong"
            value={minutes}
            onChange={(event) => setMinutes(Math.min(59, Math.max(0, Number(event.target.value))))}
          />
          <button
            type="button"
            className="h-7 rounded bg-accent-primary px-2 text-11 font-medium text-inverse disabled:opacity-50"
            disabled={busy || !total}
            onClick={() => void submit()}
          >
            Log
          </button>
          <button type="button" className="text-11 text-tertiary" onClick={() => setOpen(false)}>
            Cancel
          </button>
        </>
      ) : (
        <button
          type="button"
          className="flex items-center gap-1.5 text-12 text-tertiary hover:text-secondary"
          onClick={() => setOpen(true)}
        >
          <Timer className="size-3.5" />
          Log time
        </button>
      )}
    </div>
  );
}
