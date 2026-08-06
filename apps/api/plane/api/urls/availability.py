# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.api.views.availability import (
    AvailabilityCapabilityAPIEndpoint,
    AvailabilityOverlapAPIEndpoint,
    AvailabilityScheduleAPIEndpoint,
    LeaveTypeAPIEndpoint,
    MemberLeaveAPIEndpoint,
    MemberLeaveDetailAPIEndpoint,
    MemberWorkProfileDetailAPIEndpoint,
    MemberWorkProfileListAPIEndpoint,
    TeamEventAPIEndpoint,
    WorkCalendarAPIEndpoint,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/availability/capabilities/",
        AvailabilityCapabilityAPIEndpoint.as_view(),
        name="api-availability-capabilities",
    ),
    path(
        "workspaces/<str:slug>/availability/schedule/",
        AvailabilityScheduleAPIEndpoint.as_view(),
        name="api-availability-schedule",
    ),
    path(
        "workspaces/<str:slug>/availability/overlap/",
        AvailabilityOverlapAPIEndpoint.as_view(),
        name="api-availability-overlap",
    ),
    path(
        "workspaces/<str:slug>/availability/calendars/",
        WorkCalendarAPIEndpoint.as_view(),
        name="api-availability-calendars",
    ),
    path(
        "workspaces/<str:slug>/availability/profiles/",
        MemberWorkProfileListAPIEndpoint.as_view(),
        name="api-availability-profiles",
    ),
    path(
        "workspaces/<str:slug>/availability/profiles/<uuid:member_id>/",
        MemberWorkProfileDetailAPIEndpoint.as_view(),
        name="api-availability-profile-detail",
    ),
    path(
        "workspaces/<str:slug>/availability/leave-types/",
        LeaveTypeAPIEndpoint.as_view(),
        name="api-availability-leave-types",
    ),
    path(
        "workspaces/<str:slug>/availability/leaves/",
        MemberLeaveAPIEndpoint.as_view(),
        name="api-availability-leaves",
    ),
    path(
        "workspaces/<str:slug>/availability/leaves/<uuid:leave_id>/",
        MemberLeaveDetailAPIEndpoint.as_view(),
        name="api-availability-leave-detail",
    ),
    path(
        "workspaces/<str:slug>/availability/events/",
        TeamEventAPIEndpoint.as_view(),
        name="api-availability-events",
    ),
]
