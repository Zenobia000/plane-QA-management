# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Who may see the team's working hours and absences.

Lives here rather than in `plane/app/permissions/` because that package is upstream's;
adding to it widens the rebase surface for no gain, and this rule is used by exactly one
module.
"""

from rest_framework.permissions import BasePermission

from plane.db.models import WorkspaceMember

ADMIN = 20
MEMBER = 15


class WorkspaceAvailabilityPermission(BasePermission):
    """Active workspace members, guests excluded.

    `WorkspaceEntityPermission` admits a guest to every safe method, which is correct for
    entities a guest already collaborates on. Availability is not one of those. It is the
    whole team's working hours and absences, and a guest is by definition someone from
    outside who was let into one project -- so read access is scoped to ADMIN and MEMBER.

    Per-endpoint rules narrow this further: writing another member's record, or any
    allocation, requires ADMIN. Those checks belong with the endpoints that own them, not
    here, because this class cannot see whose record is being written.
    """

    def has_permission(self, request, view):
        if request.user.is_anonymous:
            return False

        return WorkspaceMember.objects.filter(
            member=request.user,
            workspace__slug=view.workspace_slug,
            role__in=[ADMIN, MEMBER],
            is_active=True,
        ).exists()
