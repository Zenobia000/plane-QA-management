/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { ExternalLink, Trash2 } from "lucide-react";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TProjectActivityEvent, TProjectOverviewLink, TProjectMilestoneSummary } from "@plane/types";

// The column behind these is a plain URLField, so anything longer is rejected by the
// serializer rather than truncated. Checking here turns a silent 400 into a hint.
const URL_MAX_LENGTH = 200;
const TITLE_MAX_LENGTH = 255;

/**
 * Pull something readable out of whatever the service threw.
 *
 * The overview service rethrows the raw DRF body, so a rejected link arrives as
 * `{url: ["Enter a valid URL."]}` rather than an Error. Anything unrecognised falls back
 * to the caller's default -- an empty toast is worse than a generic one.
 */
function readError(error: unknown, fallback: string): string {
  if (typeof error === "string") return error;
  if (error && typeof error === "object") {
    for (const value of Object.values(error as Record<string, unknown>)) {
      if (typeof value === "string") return value;
      if (Array.isArray(value) && typeof value[0] === "string") return value[0];
    }
  }
  return fallback;
}

/** Rejects what the serializer would reject anyway, before a round trip. */
function validateLink(url: string, title: string): string | null {
  if (url.length > URL_MAX_LENGTH) return `Keep the URL under ${URL_MAX_LENGTH} characters.`;
  if (title.length > TITLE_MAX_LENGTH) return `Keep the title under ${TITLE_MAX_LENGTH} characters.`;
  // The serializer prepends a scheme when one is missing, so "example.com/doc" is fine.
  // What it cannot accept is a bare word with no host at all.
  if (!/^(https?:\/\/)?[^\s/]+\.[^\s/]+/i.test(url)) return "Enter a URL, for example https://example.com.";
  return null;
}

export function LinksPanel({
  links,
  disabled,
  onAdd,
  onRemove,
}: {
  links: TProjectOverviewLink[];
  disabled: boolean;
  onAdd: (url: string, title: string) => Promise<void>;
  onRemove: (linkId: string) => Promise<void>;
}) {
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [invalid, setInvalid] = useState<string | null>(null);

  const add = async () => {
    const trimmedUrl = url.trim();
    const trimmedTitle = title.trim();
    if (!trimmedUrl) return;

    const problem = validateLink(trimmedUrl, trimmedTitle);
    if (problem) {
      setInvalid(problem);
      return;
    }

    setInvalid(null);
    setBusy(true);
    try {
      await onAdd(trimmedUrl, trimmedTitle);
      setUrl("");
      setTitle("");
    } catch (error) {
      // Without this the rejection was unhandled: the inputs kept their text and the
      // button re-enabled, which reads as the button doing nothing at all.
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Link not added",
        message: readError(error, "The link could not be saved."),
      });
    } finally {
      setBusy(false);
    }
  };

  const remove = async (linkId: string) => {
    try {
      await onRemove(linkId);
    } catch (error) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Link not removed",
        message: readError(error, "The link could not be removed."),
      });
    }
  };

  return (
    <section className="rounded border border-subtle p-4">
      <h2 className="text-13 font-medium text-primary">Links</h2>
      <ul className="mt-2 space-y-1.5">
        {links.map((link) => (
          <li key={link.id} className="flex items-center gap-2">
            <a
              href={link.url}
              target="_blank"
              rel="noreferrer"
              className="flex min-w-0 flex-1 items-center gap-1.5 text-12 text-accent-primary hover:underline"
            >
              <ExternalLink className="size-3.5 shrink-0" />
              <span className="truncate">{link.title || link.url}</span>
            </a>
            {!disabled && (
              <button
                type="button"
                aria-label={`Remove ${link.title || link.url}`}
                className="text-tertiary hover:text-danger-primary"
                onClick={() => void remove(link.id)}
              >
                <Trash2 className="size-3.5" />
              </button>
            )}
          </li>
        ))}
        {!links.length && <li className="text-12 text-tertiary">No links yet.</li>}
      </ul>

      {!disabled && (
        <div className="mt-3">
          <div className="flex gap-2">
            <input
              aria-label="Link title"
              className="h-8 w-28 rounded border border-subtle bg-surface-1 px-2 text-12 outline-none focus:border-accent-strong"
              placeholder="Title"
              value={title}
              onChange={(event) => {
                setTitle(event.target.value);
                setInvalid(null);
              }}
            />
            <input
              aria-label="Link URL"
              aria-invalid={!!invalid}
              className={`h-8 flex-1 rounded border bg-surface-1 px-2 text-12 outline-none ${
                invalid ? "border-danger-strong" : "border-subtle focus:border-accent-strong"
              }`}
              placeholder="https://"
              value={url}
              onChange={(event) => {
                setUrl(event.target.value);
                setInvalid(null);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter") void add();
              }}
            />
            <button
              type="button"
              className="h-8 rounded bg-surface-2 px-3 text-12 font-medium text-primary disabled:opacity-50"
              disabled={busy || !url.trim()}
              onClick={() => void add()}
            >
              Add
            </button>
          </div>
          {invalid && <p className="mt-1.5 text-11 text-danger-primary">{invalid}</p>}
        </div>
      )}
    </section>
  );
}

/**
 * Milestones, with how much of each is done.
 *
 * Counts rather than names alone: a milestone list without them is decoration, and the
 * reason to put one on this page is to see what is left.
 */
export function MilestonesPanel({ milestones }: { milestones: TProjectMilestoneSummary[] }) {
  if (!milestones.length) return null;

  return (
    <section className="rounded border border-subtle p-4">
      <h2 className="text-13 font-medium text-primary">Milestones</h2>
      <ul className="mt-2 space-y-2">
        {milestones.map((milestone) => (
          <li key={milestone.id}>
            <div className="flex items-baseline justify-between gap-2">
              <span className="truncate text-12 text-primary">{milestone.name}</span>
              <span className="shrink-0 text-11 text-tertiary">
                {milestone.completed}/{milestone.total}
                {milestone.target_date ? ` · ${milestone.target_date}` : ""}
              </span>
            </div>
            <div className="mt-1 h-1 overflow-hidden rounded bg-surface-2">
              <div
                className="bg-accent-solid h-full"
                style={{
                  width: milestone.total ? `${(milestone.completed / milestone.total) * 100}%` : "0%",
                }}
              />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ActivityPanel({ activities }: { activities: TProjectActivityEvent[] }) {
  return (
    <section className="rounded border border-subtle p-4">
      <h2 className="text-13 font-medium text-primary">Activity</h2>
      <ul className="mt-2 space-y-2">
        {activities.map((activity) => (
          <li key={activity.id} className="text-12 text-secondary">
            <span className="text-primary">{activity.actor?.display_name ?? "Someone"}</span> {activity.verb}{" "}
            {activity.field ?? ""}
            {activity.work_item && <span className="text-tertiary"> on {activity.work_item.name}</span>}
            <time className="ml-1 text-11 text-tertiary" dateTime={activity.created_at}>
              {new Date(activity.created_at).toLocaleDateString()}
            </time>
          </li>
        ))}
        {!activities.length && <li className="text-12 text-tertiary">Nothing has happened yet.</li>}
      </ul>
    </section>
  );
}
