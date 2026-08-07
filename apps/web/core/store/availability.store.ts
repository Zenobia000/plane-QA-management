/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { action, makeObservable, observable, runInAction } from "mobx";
import { AvailabilityService } from "@plane/services";
import type {
  TAvailabilityCapabilities,
  TAvailabilitySchedule,
  TMemberWorkProfile,
  TMemberWorkProfileInput,
  TOverlapRequest,
  TOverlapResult,
  TLeaveType,
  TMemberLeave,
  TMemberLeaveInput,
  TTeamEvent,
  TAllocationMatrix,
  TCalendarDay,
  TCalendarDayInput,
  TLeaveTypeInput,
  TWorkCalendar,
  TWorkCalendarInput,
} from "@plane/types";

const message = (error: unknown, fallback: string): string => {
  if (error instanceof Error) return error.message;
  if (typeof error === "object" && error !== null && "error" in error) {
    const detail = (error as { error: unknown }).error;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && typeof detail[0] === "string") return detail[0];
  }
  return fallback;
};

export interface IAvailabilityStore {
  capability: TAvailabilityCapabilities | null;
  schedule: TAvailabilitySchedule | null;
  overlap: TOverlapResult | null;
  calendars: TWorkCalendar[];
  profiles: Record<string, TMemberWorkProfile>;
  loading: boolean;
  scheduleLoading: boolean;
  error: string | null;
  hydratedFor: string | null;
  fetchCapabilities: (workspaceSlug: string) => Promise<void>;
  fetchSchedule: (workspaceSlug: string, from: string, to: string) => Promise<void>;
  findOverlap: (workspaceSlug: string, payload: TOverlapRequest) => Promise<void>;
  clearOverlap: () => void;
  leaveTypes: TLeaveType[];
  leaves: TMemberLeave[];
  events: TTeamEvent[];
  pendingLeaves: TMemberLeave[];
  allocations: TAllocationMatrix | null;
  calendarDays: Record<string, TCalendarDay[]>;
  createCalendar: (workspaceSlug: string, payload: TWorkCalendarInput) => Promise<boolean>;
  updateCalendar: (workspaceSlug: string, calendarId: string, payload: TWorkCalendarInput) => Promise<boolean>;
  deleteCalendar: (workspaceSlug: string, calendarId: string) => Promise<boolean>;
  fetchCalendarDays: (workspaceSlug: string, calendarId: string) => Promise<boolean>;
  addCalendarDays: (workspaceSlug: string, calendarId: string, days: TCalendarDayInput[]) => Promise<boolean>;
  removeCalendarDay: (workspaceSlug: string, calendarId: string, dayId: string) => Promise<boolean>;
  createLeaveType: (workspaceSlug: string, payload: TLeaveTypeInput) => Promise<boolean>;
  updateLeaveType: (workspaceSlug: string, typeId: string, payload: TLeaveTypeInput) => Promise<boolean>;
  fetchAllocations: (workspaceSlug: string) => Promise<void>;
  setAllocation: (workspaceSlug: string, memberId: string, projectId: string, percent: number) => Promise<boolean>;
  fetchPending: (workspaceSlug: string) => Promise<void>;
  decideLeave: (
    workspaceSlug: string,
    leaveId: string,
    decision: "approve" | "reject",
    note?: string
  ) => Promise<boolean>;
  fetchMonth: (workspaceSlug: string, from: string, to: string) => Promise<void>;
  createLeave: (workspaceSlug: string, payload: TMemberLeaveInput) => Promise<boolean>;
  cancelLeave: (workspaceSlug: string, leaveId: string) => Promise<boolean>;
  fetchSettings: (workspaceSlug: string) => Promise<void>;
  updateProfile: (workspaceSlug: string, memberId: string, payload: TMemberWorkProfileInput) => Promise<boolean>;
}

export class AvailabilityStore implements IAvailabilityStore {
  capability: TAvailabilityCapabilities | null = null;
  schedule: TAvailabilitySchedule | null = null;
  overlap: TOverlapResult | null = null;
  calendars: TWorkCalendar[] = [];
  leaveTypes: TLeaveType[] = [];
  leaves: TMemberLeave[] = [];
  pendingLeaves: TMemberLeave[] = [];
  allocations: TAllocationMatrix | null = null;
  calendarDays: Record<string, TCalendarDay[]> = {};
  events: TTeamEvent[] = [];
  profiles: Record<string, TMemberWorkProfile> = {};
  loading = false;
  scheduleLoading = false;
  error: string | null = null;
  /**
   * Which workspace's capability payload is already in memory.
   *
   * The tabs remount on every navigation between them, so without this the page would
   * blank behind a spinner each time someone switched from Hours to Time off and back.
   * Same reasoning as `TestingStore.hydratedFor`.
   */
  hydratedFor: string | null = null;
  private inflight: Promise<void> | null = null;
  /** Keyed by workspace+range, so paging back to last week does not refetch it. */
  private scheduleKey: string | null = null;
  private scopedTo: string | null = null;

  constructor(private service: AvailabilityService = new AvailabilityService()) {
    makeObservable(this, {
      capability: observable.ref,
      schedule: observable.ref,
      overlap: observable.ref,
      calendars: observable.ref,
      leaveTypes: observable.ref,
      leaves: observable.ref,
      pendingLeaves: observable.ref,
      allocations: observable.ref,
      calendarDays: observable,
      events: observable.ref,
      profiles: observable,
      loading: observable,
      scheduleLoading: observable,
      error: observable,
      hydratedFor: observable,
      fetchCapabilities: action,
      fetchSchedule: action,
      findOverlap: action,
      clearOverlap: action,
      fetchMonth: action,
      fetchPending: action,
      fetchAllocations: action,
      createCalendar: action,
      updateCalendar: action,
      deleteCalendar: action,
      fetchCalendarDays: action,
      addCalendarDays: action,
      removeCalendarDay: action,
      createLeaveType: action,
      updateLeaveType: action,
      setAllocation: action,
      decideLeave: action,
      createLeave: action,
      cancelLeave: action,
      fetchSettings: action,
      updateProfile: action,
    });
  }

  fetchCapabilities = async (workspaceSlug: string): Promise<void> => {
    runInAction(() => this.scopeTo(workspaceSlug));
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
          this.error = message(error, "Could not load the team calendar.");
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

  fetchSchedule = async (workspaceSlug: string, from: string, to: string): Promise<void> => {
    runInAction(() => this.scopeTo(workspaceSlug));
    const key = `${workspaceSlug}:${from}:${to}`;
    if (this.scheduleKey === key) return;

    runInAction(() => {
      this.scheduleLoading = true;
      this.error = null;
    });
    try {
      const schedule = await this.service.getSchedule(workspaceSlug, from, to);
      runInAction(() => {
        this.schedule = schedule;
        this.scheduleKey = key;
      });
    } catch (error) {
      runInAction(() => {
        this.schedule = null;
        this.scheduleKey = null;
        this.error = message(error, "Could not load the week.");
      });
    } finally {
      runInAction(() => {
        this.scheduleLoading = false;
      });
    }
  };

  findOverlap = async (workspaceSlug: string, payload: TOverlapRequest): Promise<void> => {
    runInAction(() => {
      this.error = null;
    });
    try {
      const overlap = await this.service.findOverlap(workspaceSlug, payload);
      runInAction(() => {
        this.overlap = overlap;
      });
    } catch (error) {
      runInAction(() => {
        this.overlap = null;
        this.error = message(error, "Could not work out a shared slot.");
      });
    }
  };

  clearOverlap = (): void => {
    this.overlap = null;
  };

  private monthKey: string | null = null;

  /**
   * Settings writes all clear the cached week and month.
   *
   * Changing a calendar, a holiday or a leave type changes who is reachable when — leaving
   * the drawn week in place would show a schedule the settings no longer produce.
   */
  private invalidateDerived() {
    this.scheduleKey = null;
    this.monthKey = null;
  }

  /**
   * Drops everything belonging to another workspace.
   *
   * The store is a root-store singleton and only `resetOnSignOut` ever rebuilt it, so
   * switching workspace left the previous one's absences rendered under the new one's member
   * list -- attributing colleagues' time off to the wrong people until the new response
   * landed, and permanently if it failed.
   */
  private scopeTo(workspaceSlug: string) {
    if (this.scopedTo === workspaceSlug) return;
    this.scopedTo = workspaceSlug;
    this.capability = null;
    this.schedule = null;
    this.overlap = null;
    this.calendars = [];
    this.leaveTypes = [];
    this.leaves = [];
    this.pendingLeaves = [];
    this.events = [];
    this.allocations = null;
    this.profiles = {};
    this.calendarDays = {};
    this.error = null;
    this.hydratedFor = null;
    this.scheduleKey = null;
    this.monthKey = null;
  }

  /**
   * Runs a write and reports whether it took.
   *
   * The boolean is the point. A caller that cannot tell a refused write from an accepted
   * one has to guess, and every one of them guessed the same way: close the form, clear
   * the draft. That throws away what somebody just typed at the exact moment the server
   * has told them it was wrong.
   */
  private async guard(work: () => Promise<void>, fallback: string): Promise<boolean> {
    try {
      await work();
      runInAction(() => {
        this.error = null;
      });
      return true;
    } catch (error) {
      runInAction(() => {
        this.error = message(error, fallback);
      });
      return false;
    }
  }

  createCalendar = async (workspaceSlug: string, payload: TWorkCalendarInput): Promise<boolean> =>
    this.guard(async () => {
      await this.service.createCalendar(workspaceSlug, payload);
      runInAction(() => this.invalidateDerived());
      await this.fetchSettings(workspaceSlug);
    }, "Could not create that calendar.");

  updateCalendar = async (workspaceSlug: string, calendarId: string, payload: TWorkCalendarInput): Promise<boolean> =>
    this.guard(async () => {
      await this.service.updateCalendar(workspaceSlug, calendarId, payload);
      runInAction(() => this.invalidateDerived());
      await this.fetchSettings(workspaceSlug);
    }, "Could not save that calendar.");

  deleteCalendar = async (workspaceSlug: string, calendarId: string): Promise<boolean> =>
    this.guard(async () => {
      await this.service.deleteCalendar(workspaceSlug, calendarId);
      runInAction(() => this.invalidateDerived());
      await this.fetchSettings(workspaceSlug);
    }, "Could not delete that calendar.");

  fetchCalendarDays = async (workspaceSlug: string, calendarId: string): Promise<boolean> =>
    this.guard(async () => {
      const days = await this.service.getCalendarDays(workspaceSlug, calendarId);
      runInAction(() => {
        this.calendarDays[calendarId] = days;
      });
    }, "Could not load holidays.");

  addCalendarDays = async (workspaceSlug: string, calendarId: string, days: TCalendarDayInput[]): Promise<boolean> =>
    this.guard(async () => {
      await this.service.setCalendarDays(workspaceSlug, calendarId, days);
      runInAction(() => this.invalidateDerived());
      await this.fetchCalendarDays(workspaceSlug, calendarId);
    }, "Could not save that day.");

  removeCalendarDay = async (workspaceSlug: string, calendarId: string, dayId: string): Promise<boolean> =>
    this.guard(async () => {
      await this.service.deleteCalendarDay(workspaceSlug, calendarId, dayId);
      runInAction(() => this.invalidateDerived());
      await this.fetchCalendarDays(workspaceSlug, calendarId);
    }, "Could not remove that day.");

  createLeaveType = async (workspaceSlug: string, payload: TLeaveTypeInput): Promise<boolean> =>
    this.guard(async () => {
      await this.service.createLeaveType(workspaceSlug, payload);
      runInAction(() => this.invalidateDerived());
      await this.fetchSettings(workspaceSlug);
    }, "Could not create that leave type.");

  updateLeaveType = async (workspaceSlug: string, typeId: string, payload: TLeaveTypeInput): Promise<boolean> =>
    this.guard(async () => {
      await this.service.updateLeaveType(workspaceSlug, typeId, payload);
      runInAction(() => this.invalidateDerived());
      await this.fetchSettings(workspaceSlug);
    }, "Could not save that leave type.");

  fetchAllocations = async (workspaceSlug: string): Promise<void> => {
    try {
      const matrix = await this.service.getAllocations(workspaceSlug);
      runInAction(() => {
        this.allocations = matrix;
      });
    } catch (error) {
      runInAction(() => {
        this.error = message(error, "Could not load allocations.");
      });
    }
  };

  setAllocation = async (
    workspaceSlug: string,
    memberId: string,
    projectId: string,
    percent: number
  ): Promise<boolean> =>
    this.guard(async () => {
      await this.service.setAllocation(workspaceSlug, memberId, projectId, percent);
      // Refetched rather than patched locally: the server owns the sum-to-100 rule, and a
      // local edit that assumed it succeeded would show a total the server rejected.
      await this.fetchAllocations(workspaceSlug);
    }, "Could not save that allocation.");

  fetchPending = async (workspaceSlug: string): Promise<void> => {
    try {
      const queue = await this.service.getPendingLeaves(workspaceSlug);
      runInAction(() => {
        this.pendingLeaves = queue;
      });
    } catch (error) {
      runInAction(() => {
        this.error = message(error, "Could not load requests waiting on you.");
      });
    }
  };

  decideLeave = async (
    workspaceSlug: string,
    leaveId: string,
    decision: "approve" | "reject",
    note = ""
  ): Promise<boolean> =>
    this.guard(async () => {
      const decided = await this.service.decideLeave(workspaceSlug, leaveId, decision, note);
      runInAction(() => {
        this.pendingLeaves = this.pendingLeaves.filter((leave) => leave.id !== leaveId);
        this.leaves = this.leaves.map((leave) => (leave.id === leaveId ? decided : leave));
        // A decision changes who is actually away, so the drawn week is stale.
        this.scheduleKey = null;
        this.monthKey = null;
      });
    }, "Could not record that decision.");

  fetchMonth = async (workspaceSlug: string, from: string, to: string): Promise<void> => {
    runInAction(() => this.scopeTo(workspaceSlug));
    const key = `${workspaceSlug}:${from}:${to}`;
    if (this.monthKey === key) return;
    try {
      const [leaveTypes, leaves, events] = await Promise.all([
        this.service.getLeaveTypes(workspaceSlug),
        this.service.getLeaves(workspaceSlug, from, to),
        this.service.getTeamEvents(workspaceSlug, from, to),
      ]);
      runInAction(() => {
        this.leaveTypes = leaveTypes;
        this.leaves = leaves;
        this.events = events;
        this.monthKey = key;
      });
    } catch (error) {
      runInAction(() => {
        this.monthKey = null;
        this.error = message(error, "Could not load time off.");
      });
    }
  };

  createLeave = async (workspaceSlug: string, payload: TMemberLeaveInput): Promise<boolean> =>
    this.guard(async () => {
      const created = await this.service.createLeave(workspaceSlug, payload);
      runInAction(() => {
        this.leaves = [...this.leaves, created];
        // An absence changes who is reachable, so the drawn week is stale.
        this.scheduleKey = null;
      });
    }, "Could not record that absence.");

  cancelLeave = async (workspaceSlug: string, leaveId: string): Promise<boolean> =>
    this.guard(async () => {
      await this.service.cancelLeave(workspaceSlug, leaveId);
      runInAction(() => {
        this.leaves = this.leaves.filter((leave) => leave.id !== leaveId);
        this.scheduleKey = null;
      });
    }, "Could not cancel that absence.");

  fetchSettings = async (workspaceSlug: string): Promise<void> => {
    try {
      const [calendars, profiles, leaveTypes] = await Promise.all([
        this.service.getCalendars(workspaceSlug),
        this.service.getProfiles(workspaceSlug),
        this.service.getLeaveTypes(workspaceSlug),
      ]);
      runInAction(() => {
        this.calendars = calendars;
        this.leaveTypes = leaveTypes;
        this.profiles = Object.fromEntries(profiles.map((profile) => [profile.member, profile]));
      });
    } catch (error) {
      runInAction(() => {
        this.error = message(error, "Could not load working hours.");
      });
    }
  };

  updateProfile = async (workspaceSlug: string, memberId: string, payload: TMemberWorkProfileInput): Promise<boolean> =>
    // Through `guard` like every other write. It was the one that rethrew instead, so the
    // six `clean()` rules on a work profile reached the person as an empty error banner and
    // an unhandled rejection.
    this.guard(async () => {
      const updated = (await this.service.updateProfile(workspaceSlug, memberId, payload)) as TMemberWorkProfile;
      runInAction(() => {
        this.profiles[memberId] = updated;
        // Declared hours changed, so the drawn week is stale.
        this.scheduleKey = null;
      });
    }, "Could not save those working hours.");
}
