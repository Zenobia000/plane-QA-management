# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""What the Project Overview reads: resource links, status updates, progress and activity.

The overview asks "how is this project doing", which is the same question
`plane/app/views/issue/epic.py` answers for a subtree, one scope up. The answer is again a
property of the work beneath, so progress here is computed rather than stored.

Three surfaces, deliberately separate:

- **links** and **updates** are ordinary project-scoped CRUD, so they are viewsets
- **progress** is derived, so it is a read-only endpoint with nothing to write back to
- **activity** is `IssueActivity` filtered by project. That table's `issue` column is
  already nullable, so a project-level event is representable without a second table and
  without the feed having to merge two independently-ordered streams under one cursor. See
  ADR 0005.

Progress counts every live work item by state group and does *not* apply the epic rollup's
leaf-only rule. The two are answering different questions: the rollup compares a summary
against the work it summarises and must not count both, whereas a project has no summary
above it -- every work item in it is one unit of its scope.
"""

# Python imports
from collections import defaultdict

# Django imports
from django.db.models import Count, Q

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import ProjectEntityPermission
from plane.app.serializers import EntityUpdateSerializer, MilestoneSerializer, ProjectLinkSerializer
from plane.app.views.base import BaseAPIView, BaseViewSet
from plane.db.models import EntityUpdate, Issue, IssueActivity, Milestone, ProjectLink

STATE_GROUPS = ("backlog", "unstarted", "started", "completed", "cancelled")


class ProjectLinkViewSet(BaseViewSet):
    permission_classes = [ProjectEntityPermission]

    model = ProjectLink
    serializer_class = ProjectLinkSerializer

    def perform_create(self, serializer):
        serializer.save(project_id=self.kwargs.get("project_id"))

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(workspace__slug=self.kwargs.get("slug"))
            .filter(project_id=self.kwargs.get("project_id"))
            .filter(
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
                project__archived_at__isnull=True,
            )
            .order_by("-created_at")
            .distinct()
        )


class EntityUpdateViewSet(BaseViewSet):
    """Updates for one entity, named by the query string rather than by the URL.

    `?entity_name=project` with no identifier means this project, which is the overview's
    case and saves the client from restating the id it is already addressing. A work item
    names itself: `?entity_name=work_item&entity_identifier=<uuid>`.

    The list is the top of the thread. `?parent=<uuid>` fetches one update's replies
    instead; without the distinction a reply would render beside the update it answers, and
    a thread would read as a flat run of unrelated status posts.
    """

    permission_classes = [ProjectEntityPermission]

    model = EntityUpdate
    serializer_class = EntityUpdateSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["project_id"] = self.kwargs.get("project_id")
        return context

    def perform_create(self, serializer):
        serializer.save(project_id=self.kwargs.get("project_id"), actor=self.request.user)

    def get_queryset(self):
        project_id = self.kwargs.get("project_id")
        entity_name = self.request.query_params.get("entity_name", EntityUpdate.EntityName.PROJECT)
        entity_identifier = self.request.query_params.get("entity_identifier") or project_id
        parent = self.request.query_params.get("parent")

        return (
            super()
            .get_queryset()
            .filter(workspace__slug=self.kwargs.get("slug"))
            .filter(project_id=project_id)
            .filter(entity_name=entity_name, entity_identifier=entity_identifier)
            .filter(**({"parent_id": parent} if parent else {"parent__isnull": True}))
            .filter(
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
            )
            .select_related("actor")
            .annotate(reply_count=Count("replies", distinct=True))
            .order_by("-created_at")
            .distinct()
        )


class MilestoneViewSet(BaseViewSet):
    """Milestones, writable by the browser.

    They existed only on the token API until now, so the overview could render them and no
    one could create, rename or retire one without an API key -- the demo seed produced
    milestones a reader could see and had no way to manage.

    `work_item_count` is annotated rather than counted per row so the list stays one query,
    and it is what `destroy` enforces against: a milestone still carrying work is a
    commitment someone is measured on, and deleting it would silently unset their target.
    """

    permission_classes = [ProjectEntityPermission]

    model = Milestone
    serializer_class = MilestoneSerializer

    def perform_create(self, serializer):
        serializer.save(project_id=self.kwargs.get("project_id"))

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(workspace__slug=self.kwargs.get("slug"))
            .filter(project_id=self.kwargs.get("project_id"))
            .filter(
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
                project__archived_at__isnull=True,
            )
            .annotate(
                work_item_count=Count("work_items", filter=Q(work_items__deleted_at__isnull=True), distinct=True)
            )
            .order_by("target_date", "sort_order", "created_at")
            .distinct()
        )

    def destroy(self, request, slug, project_id, pk):
        milestone = self.get_queryset().get(pk=pk)
        if Issue.issue_objects.filter(milestone_id=pk).exists():
            return Response(
                {"error": "A milestone assigned to work items cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        milestone.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectProgressEndpoint(BaseAPIView):
    """Work item counts by state group, which is the overview's completion bar."""

    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        counts = dict.fromkeys(STATE_GROUPS, 0)
        rows = (
            Issue.issue_objects.filter(project_id=project_id, workspace__slug=slug)
            .values("state__group")
            .annotate(count=Count("id"))
        )
        for row in rows:
            group = row["state__group"]
            if group in counts:
                counts[group] += row["count"]

        total = sum(counts.values())
        # Cancelled work is out of scope rather than outstanding, so it is excluded from the
        # denominator. Reporting 8/10 complete because two items were cancelled would
        # describe a project as behind when nothing is owed.
        in_scope = total - counts["cancelled"]
        return Response(
            {
                "state_distribution": counts,
                "total": total,
                "in_scope": in_scope,
                "completed": counts["completed"],
                "completion_percentage": round(counts["completed"] / in_scope * 100) if in_scope else 0,
            }
        )


class ProjectActivityEndpoint(BaseAPIView):
    """The project's activity stream, work-item events included.

    One query over `issue_activities` rather than a merge of two tables: rows about a work
    item carry `issue`, rows about the project itself do not, and both are already
    project-scoped and ordered by the same column.
    """

    permission_classes = [ProjectEntityPermission]

    # `paginate` defaults to a thousand rows a page, which for an activity feed is not a
    # page at all -- `issue_activities` gains a row per field change per work item, so a
    # real project reaches that within days and the overview rendered every one. A page is
    # what fits on screen; the client asks for more by cursor.
    PER_PAGE = 20

    def get(self, request, slug, project_id):
        activities = (
            IssueActivity.objects.filter(project_id=project_id, workspace__slug=slug)
            .select_related("actor", "issue")
            .order_by("-created_at")
        )
        return self.paginate(
            request=request,
            queryset=activities,
            default_per_page=self.PER_PAGE,
            on_results=lambda results: [
                {
                    "id": str(activity.id),
                    "verb": activity.verb,
                    "field": activity.field,
                    "old_value": activity.old_value,
                    "new_value": activity.new_value,
                    "comment": activity.comment,
                    "created_at": activity.created_at,
                    "actor": (
                        {
                            "id": str(activity.actor_id),
                            "display_name": activity.actor.display_name,
                            "avatar_url": activity.actor.avatar_url,
                        }
                        if activity.actor
                        else None
                    ),
                    "work_item": (
                        {"id": str(activity.issue_id), "name": activity.issue.name} if activity.issue else None
                    ),
                }
                for activity in results
            ],
        )


class ProjectOverviewEndpoint(BaseAPIView):
    """Everything the overview needs that is not already on the project payload.

    One request rather than four. The page renders as a unit and every part of it is cheap;
    four round trips would only buy the ability to render a quarter of a screen sooner.
    """

    permission_classes = [ProjectEntityPermission]

    # The overview embeds the newest updates rather than the whole thread, which on a long
    # running project is most of a page on its own. `updates_total` tells the client what it
    # is not being shown, so it can offer the rest through the updates endpoint instead of
    # silently truncating.
    EMBEDDED_UPDATES = 10

    def get(self, request, slug, project_id):
        progress = ProjectProgressEndpoint().get(request, slug, project_id).data
        links = ProjectLink.objects.filter(project_id=project_id, workspace__slug=slug).order_by("-created_at")
        thread = (
            EntityUpdate.objects.filter(
                project_id=project_id,
                workspace__slug=slug,
                entity_name=EntityUpdate.EntityName.PROJECT,
                entity_identifier=project_id,
                parent__isnull=True,
            )
            .select_related("actor")
            .annotate(reply_count=Count("replies", distinct=True))
            .order_by("-created_at")
        )
        updates = thread[: self.EMBEDDED_UPDATES]

        return Response(
            {
                "progress": progress,
                "links": ProjectLinkSerializer(links, many=True).data,
                "updates": EntityUpdateSerializer(updates, many=True).data,
                "updates_total": thread.count(),
                "milestones": self._milestones(slug, project_id),
            },
            status=status.HTTP_200_OK,
        )

    def _milestones(self, slug, project_id):
        """Read-only, and built here rather than through a serializer.

        Milestones are this fork's own model and today they have endpoints on the token API
        only. The overview needs to *show* them, which is five fields and two counts, so it
        reads them directly instead of growing an app-API viewset that nothing else wants
        yet. A milestone with no counts would be decoration -- the reason to put one on this
        page is to see how much of it is done.
        """
        # Counted in one grouped pass rather than as two annotations on `Milestone`.
        # Two aggregates over the same multi-valued relation make Django reuse one join for
        # the unfiltered count and add another for the filtered one, and the result is a
        # cross product -- a milestone with one done item out of two reported two done. The
        # progress endpoint above groups for the same reason.
        counts = defaultdict(lambda: {"total": 0, "completed": 0})
        for row in (
            Issue.issue_objects.filter(project_id=project_id, milestone__isnull=False)
            .values("milestone_id", "state__group")
            .annotate(count=Count("id"))
        ):
            bucket = counts[row["milestone_id"]]
            bucket["total"] += row["count"]
            if row["state__group"] == "completed":
                bucket["completed"] += row["count"]

        milestones = Milestone.objects.filter(project_id=project_id, workspace__slug=slug).order_by(
            "target_date", "sort_order", "created_at"
        )
        return [
            {
                "id": str(milestone.id),
                "name": milestone.name,
                "status": milestone.status,
                "target_date": milestone.target_date,
                "total": counts[milestone.id]["total"],
                "completed": counts[milestone.id]["completed"],
            }
            for milestone in milestones
        ]
