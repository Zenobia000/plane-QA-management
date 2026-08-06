# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""The API-key mirror of the team calendar.

Thin subclasses only. Every handler is the app-tree one; this layer adds authentication,
throttling and the error envelope and nothing else, so there is exactly one implementation
of "when is this person reachable" no matter which door the question arrives through.

The mixin is imported rather than copied. Its name says Testing for historical reasons --
it predates this module -- but it carries no Testing-specific behaviour, and duplicating an
error envelope is how two envelopes drift apart.
"""

from plane.app.views.availability import (
    AllocationMatrixEndpoint as AppAllocationMatrixEndpoint,
    AvailabilityCapabilityEndpoint as AppAvailabilityCapabilityEndpoint,
    CycleCapacityEndpoint as AppCycleCapacityEndpoint,
    AvailabilityOverlapEndpoint as AppAvailabilityOverlapEndpoint,
    AvailabilityScheduleEndpoint as AppAvailabilityScheduleEndpoint,
    LeaveTypeListCreateEndpoint as AppLeaveTypeListCreateEndpoint,
    MemberLeaveDetailEndpoint as AppMemberLeaveDetailEndpoint,
    MemberLeaveListCreateEndpoint as AppMemberLeaveListCreateEndpoint,
    PendingLeaveEndpoint as AppPendingLeaveEndpoint,
    MemberWorkProfileDetailEndpoint as AppMemberWorkProfileDetailEndpoint,
    MemberWorkProfileListEndpoint as AppMemberWorkProfileListEndpoint,
    TeamEventListCreateEndpoint as AppTeamEventListCreateEndpoint,
    WorkCalendarListCreateEndpoint as AppWorkCalendarListCreateEndpoint,
)

from .testing import APIKeyTestingEndpointMixin as APIKeyEndpointMixin


class AvailabilityCapabilityAPIEndpoint(APIKeyEndpointMixin, AppAvailabilityCapabilityEndpoint):
    pass


class AvailabilityScheduleAPIEndpoint(APIKeyEndpointMixin, AppAvailabilityScheduleEndpoint):
    pass


class AvailabilityOverlapAPIEndpoint(APIKeyEndpointMixin, AppAvailabilityOverlapEndpoint):
    pass


class WorkCalendarAPIEndpoint(APIKeyEndpointMixin, AppWorkCalendarListCreateEndpoint):
    pass


class MemberWorkProfileListAPIEndpoint(APIKeyEndpointMixin, AppMemberWorkProfileListEndpoint):
    pass


class MemberWorkProfileDetailAPIEndpoint(APIKeyEndpointMixin, AppMemberWorkProfileDetailEndpoint):
    pass


class LeaveTypeAPIEndpoint(APIKeyEndpointMixin, AppLeaveTypeListCreateEndpoint):
    pass


class MemberLeaveAPIEndpoint(APIKeyEndpointMixin, AppMemberLeaveListCreateEndpoint):
    pass


class MemberLeaveDetailAPIEndpoint(APIKeyEndpointMixin, AppMemberLeaveDetailEndpoint):
    pass


class TeamEventAPIEndpoint(APIKeyEndpointMixin, AppTeamEventListCreateEndpoint):
    pass


class PendingLeaveAPIEndpoint(APIKeyEndpointMixin, AppPendingLeaveEndpoint):
    pass


class AllocationMatrixAPIEndpoint(APIKeyEndpointMixin, AppAllocationMatrixEndpoint):
    pass


class CycleCapacityAPIEndpoint(APIKeyEndpointMixin, AppCycleCapacityEndpoint):
    pass
