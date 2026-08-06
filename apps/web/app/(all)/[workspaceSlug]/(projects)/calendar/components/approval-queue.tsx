/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { Check, X } from "lucide-react";
import { useParams } from "react-router";
import { useTranslation } from "@plane/i18n";
import { useAvailability } from "@/hooks/store/use-availability";
import { useMember } from "@/hooks/store/use-member";

/**
 * Requests this person is on the hook for.
 *
 * Rendered only when the queue is non-empty. An always-present "0 waiting" panel trains
 * people to stop looking at the spot, which is the opposite of what an approval queue is
 * for.
 */
export const ApprovalQueue = observer(function ApprovalQueue() {
  const { t } = useTranslation();
  const { workspaceSlug } = useParams();
  const slug = workspaceSlug?.toString() ?? "";
  const { pendingLeaves, leaveTypes, fetchPending, decideLeave } = useAvailability();
  const { getUserDetails } = useMember();
  const [note, setNote] = useState("");

  useEffect(() => {
    if (slug) void fetchPending(slug);
  }, [fetchPending, slug]);

  if (pendingLeaves.length === 0) return null;

  const typeName = (id: string) => leaveTypes.find((type) => type.id === id)?.name ?? "";

  return (
    <section className="flex flex-col gap-2 rounded-lg border border-warning-subtle bg-warning-subtle p-3">
      <h3 className="text-13 font-medium text-primary">
        {t("team_calendar.approvals.title")} ({pendingLeaves.length})
      </h3>

      <ul className="flex flex-col gap-2">
        {pendingLeaves.map((leave) => {
          const details = getUserDetails(leave.member);
          return (
            <li key={leave.id} className="flex flex-wrap items-center gap-2 text-13">
              <span className="text-primary">{details?.display_name || details?.email || leave.member}</span>
              <span className="text-secondary">
                {t("team_calendar.approvals.requested")} {typeName(leave.leave_type)} {leave.start_date}
                {leave.end_date !== leave.start_date && ` – ${leave.end_date}`}
              </span>
              {/* Present only because the reader is entitled to it; the API omits the key
                  entirely for anyone else. */}
              {leave.reason && <span className="text-tertiary">“{leave.reason}”</span>}
              <button
                type="button"
                onClick={() => void decideLeave(slug, leave.id, "approve", note)}
                className="flex items-center gap-1 rounded bg-success-subtle px-2 py-1 text-12 text-success-primary"
              >
                <Check className="size-3" />
                {t("team_calendar.approvals.approve")}
              </button>
              <button
                type="button"
                onClick={() => void decideLeave(slug, leave.id, "reject", note)}
                className="flex items-center gap-1 rounded bg-danger-subtle px-2 py-1 text-12 text-danger-primary"
              >
                <X className="size-3" />
                {t("team_calendar.approvals.reject")}
              </button>
            </li>
          );
        })}
      </ul>

      <input
        type="text"
        value={note}
        onChange={(event) => setNote(event.target.value)}
        placeholder={t("team_calendar.approvals.note")}
        className="rounded border border-subtle bg-surface-1 px-2 py-1 text-12"
      />
    </section>
  );
});
