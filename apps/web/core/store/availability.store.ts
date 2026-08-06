/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { action, makeObservable, observable, runInAction } from "mobx";
import { AvailabilityService } from "@plane/services";
import type { TAvailabilityCapabilities } from "@plane/types";

export interface IAvailabilityStore {
  capability: TAvailabilityCapabilities | null;
  loading: boolean;
  error: string | null;
  hydratedFor: string | null;
  fetchCapabilities: (workspaceSlug: string) => Promise<void>;
}

export class AvailabilityStore implements IAvailabilityStore {
  capability: TAvailabilityCapabilities | null = null;
  loading = false;
  error: string | null = null;
  /**
   * Which workspace's capability payload is already in memory.
   *
   * The tabs remount on every navigation between them, so without this the page would
   * blank behind a spinner each time someone switched from Schedule to Leave and back.
   * Same reasoning as `TestingStore.hydratedFor`.
   */
  hydratedFor: string | null = null;
  private inflight: Promise<void> | null = null;

  constructor(private service: AvailabilityService = new AvailabilityService()) {
    makeObservable(this, {
      capability: observable.ref,
      loading: observable,
      error: observable,
      hydratedFor: observable,
      fetchCapabilities: action,
    });
  }

  fetchCapabilities = async (workspaceSlug: string): Promise<void> => {
    if (this.hydratedFor === workspaceSlug) return;
    // A second tab mounting while the first request is open must not fire another.
    if (this.inflight) return this.inflight;

    const request = (async () => {
      runInAction(() => {
        this.loading = true;
        this.error = null;
      });
      try {
        const capability = await this.service.getCapabilities(workspaceSlug);
        runInAction(() => {
          this.capability = capability;
          this.hydratedFor = workspaceSlug;
        });
      } catch (error) {
        runInAction(() => {
          this.capability = null;
          this.hydratedFor = null;
          this.error = error instanceof Error ? error.message : "Could not load the team calendar.";
        });
      } finally {
        runInAction(() => {
          this.loading = false;
        });
        this.inflight = null;
      }
    })();

    this.inflight = request;
    return request;
  };
}
