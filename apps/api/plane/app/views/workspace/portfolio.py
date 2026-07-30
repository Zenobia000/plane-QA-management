# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Initiatives and teamspaces, on the surface the web client actually uses.

Both already had somewhere to live. `Initiative` and `InitiativeProject` shipped in
`db/models/portfolio.py` with CRUD on the token API only, which the session-authenticated web
client cannot reach; `Team` shipped in `db/models/workspace.py` referenced by nothing. What
was missing in each case was the app-API surface and, for initiatives, the one thing that
makes the level above a project worth having -- a rollup.

The initiative rollup counts work items across every member project, and it counts them the
way `ProjectProgressEndpoint` does rather than the way the epic rollup does. The distinction
is the same one recorded there: the epic rollup compares a summary against the work it
summarises and must not count both, whereas an initiative has no summary beneath it -- every
work item in every member project is one unit of its scope.
"""

# Django imports
from django.db.models import Count

# Third party imports
from rest_framework import serializers, status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import WorkSpaceAdminPermission, WorkspaceEntityPermission
from plane.app.serializers.base import BaseSerializer
from plane.app.views.base import BaseAPIView, BaseViewSet
from plane.db.models import (
    Initiative,
    InitiativeProject,
    Issue,
    Project,
    Team,
    TeamMember,
    TeamProject,
    Workspace,
)

STATE_GROUPS = ("backlog", "unstarted", "started", "completed", "cancelled")


class InitiativeSerializer(BaseSerializer):
    project_ids = serializers.SerializerMethodField()

    class Meta:
        model = Initiative
        fields = "__all__"
        read_only_fields = ["workspace"]

    def get_project_ids(self, obj):
        return [str(link.project_id) for link in obj.initiative_projects.all()]


class TeamSerializer(BaseSerializer):
    member_ids = serializers.SerializerMethodField()
    project_ids = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = "__all__"
        read_only_fields = ["workspace"]

    def get_member_ids(self, obj):
        return [str(link.member_id) for link in obj.members.all()]

    def get_project_ids(self, obj):
        return [str(link.project_id) for link in obj.projects.all()]


class _WorkspaceScoped(BaseViewSet):
    """Shared plumbing: everything here is addressed by slug and owned by a workspace."""

    permission_classes = [WorkspaceEntityPermission]

    def _workspace(self):
        return Workspace.objects.get(slug=self.kwargs.get("slug"))

    def get_queryset(self):
        return super().get_queryset().filter(workspace__slug=self.kwargs.get("slug"))

    def perform_create(self, serializer):
        serializer.save(workspace=self._workspace())


class InitiativeViewSet(_WorkspaceScoped):
    model = Initiative
    serializer_class = InitiativeSerializer

    def get_queryset(self):
        return super().get_queryset().prefetch_related("initiative_projects")


class InitiativeProjectEndpoint(BaseAPIView):
    """Which projects an initiative covers.

    Membership is replaced rather than appended, because the request states the whole set.
    Appending would make removing a project impossible through the call that adds one.
    """

    permission_classes = [WorkspaceEntityPermission]

    def post(self, request, slug, initiative_id):
        initiative = Initiative.objects.filter(pk=initiative_id, workspace__slug=slug).first()
        if not initiative:
            return Response({"error": "The initiative does not exist."}, status=status.HTTP_404_NOT_FOUND)

        project_ids = request.data.get("project_ids", [])
        valid = list(
            Project.objects.filter(pk__in=project_ids, workspace__slug=slug).values_list("id", flat=True)
        )
        # A project from another workspace is dropped rather than refused: the caller named a
        # set, and the part of it this workspace can honour is unambiguous.
        dropped = [str(pid) for pid in project_ids if str(pid) not in {str(v) for v in valid}]

        InitiativeProject.objects.filter(initiative=initiative).delete()
        InitiativeProject.objects.bulk_create(
            [
                InitiativeProject(initiative=initiative, project_id=pid, workspace=initiative.workspace)
                for pid in valid
            ],
            batch_size=100,
        )
        return Response({"project_ids": [str(v) for v in valid], "dropped": dropped}, status=status.HTTP_200_OK)


class InitiativeProgressEndpoint(BaseAPIView):
    """Work item counts across every project the initiative covers."""

    permission_classes = [WorkspaceEntityPermission]

    def get(self, request, slug, initiative_id):
        project_ids = list(
            InitiativeProject.objects.filter(initiative_id=initiative_id, workspace__slug=slug).values_list(
                "project_id", flat=True
            )
        )
        counts = dict.fromkeys(STATE_GROUPS, 0)
        if project_ids:
            for row in (
                Issue.issue_objects.filter(project_id__in=project_ids)
                .values("state__group")
                .annotate(count=Count("id"))
            ):
                if row["state__group"] in counts:
                    counts[row["state__group"]] += row["count"]

        total = sum(counts.values())
        # Cancelled work is out of scope rather than outstanding, the same denominator the
        # project overview uses so the two levels cannot report different percentages of the
        # same work.
        in_scope = total - counts["cancelled"]
        return Response(
            {
                "project_count": len(project_ids),
                "state_distribution": counts,
                "total": total,
                "in_scope": in_scope,
                "completed": counts["completed"],
                "completion_percentage": round(counts["completed"] / in_scope * 100) if in_scope else 0,
            },
            status=status.HTTP_200_OK,
        )


class TeamViewSet(_WorkspaceScoped):
    permission_classes = [WorkSpaceAdminPermission]
    model = Team
    serializer_class = TeamSerializer

    def get_queryset(self):
        return super().get_queryset().prefetch_related("members", "projects")


class TeamMembershipEndpoint(BaseAPIView):
    """A teamspace's members and the projects it covers, both replaced as a set."""

    permission_classes = [WorkSpaceAdminPermission]

    def post(self, request, slug, team_id):
        team = Team.objects.filter(pk=team_id, workspace__slug=slug).first()
        if not team:
            return Response({"error": "The teamspace does not exist."}, status=status.HTTP_404_NOT_FOUND)

        if "member_ids" in request.data:
            valid_members = list(
                team.workspace.workspace_member.filter(
                    member_id__in=request.data["member_ids"], is_active=True
                ).values_list("member_id", flat=True)
            )
            TeamMember.objects.filter(team=team).delete()
            TeamMember.objects.bulk_create(
                [TeamMember(team=team, member_id=mid, workspace=team.workspace) for mid in valid_members],
                batch_size=100,
            )

        if "project_ids" in request.data:
            valid_projects = list(
                Project.objects.filter(pk__in=request.data["project_ids"], workspace=team.workspace).values_list(
                    "id", flat=True
                )
            )
            TeamProject.objects.filter(team=team).delete()
            TeamProject.objects.bulk_create(
                [TeamProject(team=team, project_id=pid, workspace=team.workspace) for pid in valid_projects],
                batch_size=100,
            )

        return Response(TeamSerializer(team).data, status=status.HTTP_200_OK)
