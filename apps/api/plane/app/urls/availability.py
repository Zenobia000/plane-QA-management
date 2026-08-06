# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views.availability import (
    AllocationMatrixEndpoint,
    AvailabilityCapabilityEndpoint,
    CycleCapacityEndpoint,
    AvailabilityOverlapEndpoint,
    AvailabilityScheduleEndpoint,
    LeaveTypeListCreateEndpoint,
    MemberLeaveDetailEndpoint,
    MemberLeaveListCreateEndpoint,
    MemberWorkProfileDetailEndpoint,
    MemberWorkProfileListEndpoint,
    PendingLeaveEndpoint,
    TeamEventListCreateEndpoint,
    WorkCalendarListCreateEndpoint,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/availability/capabilities/",
        AvailabilityCapabilityEndpoint.as_view(),
        name="availability-capabilities",
    ),
    path(
        "workspaces/<str:slug>/availability/schedule/",
        AvailabilityScheduleEndpoint.as_view(),
        name="availability-schedule",
    ),
    path(
        "workspaces/<str:slug>/availability/overlap/",
        AvailabilityOverlapEndpoint.as_view(),
        name="availability-overlap",
    ),
    path(
        "workspaces/<str:slug>/availability/calendars/",
        WorkCalendarListCreateEndpoint.as_view(),
        name="availability-calendars",
    ),
    path(
        "workspaces/<str:slug>/availability/profiles/",
        MemberWorkProfileListEndpoint.as_view(),
        name="availability-profiles",
    ),
    path(
        "workspaces/<str:slug>/availability/profiles/<uuid:member_id>/",
        MemberWorkProfileDetailEndpoint.as_view(),
        name="availability-profile-detail",
    ),
    path(
        "workspaces/<str:slug>/availability/leave-types/",
        LeaveTypeListCreateEndpoint.as_view(),
        name="availability-leave-types",
    ),
    path(
        "workspaces/<str:slug>/availability/leaves/",
        MemberLeaveListCreateEndpoint.as_view(),
        name="availability-leaves",
    ),
    path(
        "workspaces/<str:slug>/availability/leaves/<uuid:leave_id>/",
        MemberLeaveDetailEndpoint.as_view(),
        name="availability-leave-detail",
    ),
    path(
        "workspaces/<str:slug>/availability/events/",
        TeamEventListCreateEndpoint.as_view(),
        name="availability-events",
    ),
    path(
        "workspaces/<str:slug>/availability/leaves/pending/",
        PendingLeaveEndpoint.as_view(),
        name="availability-pending-leaves",
    ),
    path(
        "workspaces/<str:slug>/availability/allocations/",
        AllocationMatrixEndpoint.as_view(),
        name="availability-allocations",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/cycles/<uuid:cycle_id>/capacity/",
        CycleCapacityEndpoint.as_view(),
        name="availability-cycle-capacity",
    ),
]
