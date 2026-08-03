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
from django.db.models import Case, Count, F, IntegerField, Q, Value, When
from django.utils import timezone

# Third party imports
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

# Module imports
from plane.app.permissions import ROLE, ProjectEntityPermission
from plane.app.serializers import EntityUpdateSerializer, MilestoneSerializer, ProjectLinkSerializer
from plane.app.views.base import BaseAPIView, BaseViewSet
from plane.db.models import (
    EntityUpdate,
    EntityUpdateLabel,
    IntakeIssue,
    Issue,
    IssueActivity,
    IssueAssignee,
    Milestone,
    ProjectLink,
    ProjectMember,
    WorkItemProperty,
    WorkItemPropertyValue,
)
from plane.db.models.intake import IntakeIssueStatus

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
        label_ids = serializer.validated_data.pop("label_ids", [])
        update = serializer.save(project_id=self.kwargs.get("project_id"), actor=self.request.user)
        self._set_labels(update, label_ids)

    def perform_update(self, serializer):
        label_ids = serializer.validated_data.pop("label_ids", None)
        # Only a rewrite of what the update says counts as an edit. Attaching a topic is
        # filing, not revision, and should not put "edited" on somebody else's announcement.
        edited = "description" in serializer.validated_data and (
            serializer.validated_data["description"] != serializer.instance.description
        )
        update = serializer.save(**({"edited_at": timezone.now()} if edited else {}))
        if label_ids is not None:
            self._set_labels(update, label_ids)

    def _set_labels(self, update, label_ids):
        """Replace the update's topics with exactly this set."""
        wanted = {str(label_id) for label_id in label_ids}
        existing = {str(link.label_id): link for link in update.labels.all()}

        for label_id, link in existing.items():
            if label_id not in wanted:
                link.delete()
        # `workspace_id` is set by hand because `bulk_create` skips `save()`, and
        # `ProjectBaseModel.save()` is the only thing that normally derives it.
        EntityUpdateLabel.objects.bulk_create(
            [
                EntityUpdateLabel(
                    entity_update=update,
                    label_id=label_id,
                    project_id=update.project_id,
                    workspace_id=update.workspace_id,
                )
                for label_id in wanted
                if label_id not in existing
            ]
        )

    def destroy(self, request, slug, project_id, pk):
        update = self.get_queryset().get(pk=pk)
        self._assert_may_change(update)
        update.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def partial_update(self, request, slug, project_id, pk):
        self._assert_may_change(self.get_queryset().get(pk=pk))
        return super().partial_update(request, slug, project_id, pk)

    def _assert_may_change(self, update):
        """An announcement belongs to whoever posted it, or to a project admin.

        Editing someone else's post on a shared noticeboard changes what they are recorded
        as having said. Admins keep the ability because a board nobody can moderate is its
        own problem.
        """
        if update.actor_id == self.request.user.id:
            return
        is_admin = ProjectMember.objects.filter(
            project_id=update.project_id,
            member=self.request.user,
            role=ROLE.ADMIN.value,
            is_active=True,
        ).exists()
        if not is_admin:
            raise PermissionDenied("Only the author or a project admin can change this update.")

    def get_queryset(self):
        project_id = self.kwargs.get("project_id")
        entity_name = self.request.query_params.get("entity_name", EntityUpdate.EntityName.PROJECT)
        entity_identifier = self.request.query_params.get("entity_identifier") or project_id
        parent = self.request.query_params.get("parent")
        # Topic filter. Absent means every topic, which is what the board opens on.
        label = self.request.query_params.get("label")

        queryset = (
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
            .prefetch_related("labels")
            .annotate(reply_count=Count("replies", distinct=True))
            .order_by("-created_at")
            .distinct()
        )
        if label:
            queryset = queryset.filter(labels__label_id=label, labels__deleted_at__isnull=True)
        return queryset


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
            .prefetch_related("labels")
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


class ProjectFrontlineEndpoint(BaseAPIView):
    """Intake, grouped by whichever dimension the project decided matters.

    The question this answers is the one a product manager opens the overview for: which
    customers are complaining, about what, and has anyone picked it up. Intake already holds
    the raw material -- everything filed from outside the team lands there with a source and
    a status -- but as a flat list it answers "how many" and never "whose".

    Nothing here names a category. The grouping property is whatever a project marked with
    `is_grouping_dimension`, so the row headings read Acme and Globex on one project and
    APAC and EMEA on the next, and the panel's own title comes from the property's name. A
    hardcoded "customer" field would have been wrong for every team that thinks in tenants,
    regions or pilot cohorts -- and there is no reason to make them all think in ours.

    Returns `dimension: null` when no property is marked, which is the signal for the panel
    to stay off the page rather than render an empty frame.
    """

    permission_classes = [ProjectEntityPermission]

    # Per group, so one noisy account cannot push every other group off the screen. The
    # group's own `total` says what is being held back; `open_intake` goes to the rest.
    ITEMS_PER_GROUP = 5

    #: Intake statuses, folded into the three answers a reader wants.
    TRIAGE = {
        IntakeIssueStatus.PENDING: "pending",
        IntakeIssueStatus.SNOOZED: "pending",
        IntakeIssueStatus.ACCEPTED: "accepted",
        IntakeIssueStatus.REJECTED: "declined",
        IntakeIssueStatus.DUPLICATE: "declined",
    }

    def get(self, request, slug, project_id):
        dimension = WorkItemProperty.objects.filter(
            project_id=project_id,
            workspace__slug=slug,
            is_grouping_dimension=True,
            is_active=True,
            deleted_at__isnull=True,
        ).first()
        if dimension is None:
            return Response({"dimension": None, "groups": [], "totals": self._empty_totals()})

        intake_rows = list(
            IntakeIssue.objects.filter(project_id=project_id, workspace__slug=slug)
            .select_related("issue", "issue__state")
            .order_by("-created_at")
        )
        issue_ids = [row.issue_id for row in intake_rows]

        labels = {option.value: option.label for option in dimension.options.all()}
        buckets = self._group(intake_rows, self._dimension_values(dimension, issue_ids))

        return Response(
            {
                "dimension": {
                    "id": str(dimension.id),
                    "name": dimension.name,
                    "kind": dimension.kind,
                },
                "groups": [
                    {
                        "value": value,
                        # Falls back to the raw value for a group whose option was renamed
                        # or removed: dropping the row would hide work that still exists.
                        "label": labels.get(value, value) if value is not None else None,
                        "total": len(rows),
                        **self._counts(rows),
                        "items": [self._item(row) for row in rows[: self.ITEMS_PER_GROUP]],
                    }
                    for value, rows in buckets
                ],
                "totals": self._counts(intake_rows),
            }
        )

    def _dimension_values(self, dimension, issue_ids):
        """issue id -> the values it carries on the grouping property.

        A list either way. A multi-select puts one work item under several headings, which
        is the honest rendering of a bug two customers reported.
        """
        values = {}
        for property_value in WorkItemPropertyValue.objects.filter(
            property=dimension, issue_id__in=issue_ids, deleted_at__isnull=True
        ):
            raw = property_value.value
            if raw is None or raw == "":
                continue
            values[property_value.issue_id] = raw if isinstance(raw, list) else [raw]
        return values

    def _group(self, intake_rows, values):
        """Buckets in descending size, with the untagged pile last.

        Untagged is deliberately kept rather than dropped. It is the pile that says how much
        of the intake nobody has attributed yet, and a panel that hides it reports a
        tidier project than the one that exists.
        """
        buckets = defaultdict(list)
        for row in intake_rows:
            for value in values.get(row.issue_id) or [None]:
                buckets[value].append(row)
        return sorted(buckets.items(), key=lambda item: (item[0] is None, -len(item[1]), str(item[0] or "")))

    def _counts(self, rows):
        counts = self._empty_totals()
        for row in rows:
            counts[self.TRIAGE.get(row.status, "pending")] += 1
        return counts

    def _empty_totals(self):
        return {"pending": 0, "accepted": 0, "declined": 0}

    def _item(self, row):
        return {
            "id": str(row.id),
            "issue_id": str(row.issue_id),
            "name": row.issue.name,
            "sequence_id": row.issue.sequence_id,
            "status": row.status,
            "triage": self.TRIAGE.get(row.status, "pending"),
            "priority": row.issue.priority,
            "state_group": row.issue.state.group if row.issue.state_id else None,
            "source": row.source,
            "created_at": row.created_at,
        }


class ProjectAttentionEndpoint(BaseAPIView):
    """The few work items that will go wrong first.

    Overdue before urgent, because a missed date is a fact and a priority is an opinion --
    and within overdue, the oldest miss first. Everything already completed or cancelled is
    excluded: an item finished late is a retrospective, not a thing to do today.

    Capped hard. A list of forty items is a work-item view with worse filtering, and the
    reason to put this on the overview is to be readable at a glance. `total_overdue` and
    `total_urgent` say how much sits behind the cap so the number is never quietly rounded
    down to what fits.
    """

    permission_classes = [ProjectEntityPermission]

    LIMIT = 5

    #: `priority` is a CharField, so ordering by the column sorts alphabetically -- which
    #: puts "urgent" below "none" and reads as arbitrary. Ranked explicitly instead.
    PRIORITY_RANK = Case(
        When(priority="urgent", then=Value(0)),
        When(priority="high", then=Value(1)),
        When(priority="medium", then=Value(2)),
        When(priority="low", then=Value(3)),
        default=Value(4),
        output_field=IntegerField(),
    )

    def get(self, request, slug, project_id):
        today = timezone.now().date()
        live = Issue.issue_objects.filter(project_id=project_id, workspace__slug=slug).exclude(
            state__group__in=["completed", "cancelled"]
        )

        ranked = live.annotate(priority_rank=self.PRIORITY_RANK)
        # Oldest miss first; among misses of the same age, the more urgent one.
        overdue = ranked.filter(target_date__lt=today).order_by("target_date", "priority_rank", "created_at")
        # Urgent items already counted as overdue are not repeated -- the same row twice
        # reads as two problems. Ones with a date left lead, since a date is a commitment.
        urgent = (
            ranked.filter(priority="urgent")
            .exclude(target_date__lt=today)
            .order_by(F("target_date").asc(nulls_last=True), "created_at")
        )

        total_overdue = overdue.count()
        total_urgent = urgent.count()
        rows = list(overdue.select_related("state")[: self.LIMIT])
        if len(rows) < self.LIMIT:
            rows += list(urgent.select_related("state")[: self.LIMIT - len(rows)])

        assignees = defaultdict(list)
        for link in (
            IssueAssignee.objects.filter(issue_id__in=[row.id for row in rows])
            .select_related("assignee")
            .order_by("created_at")
        ):
            assignees[link.issue_id].append(
                {
                    "id": str(link.assignee_id),
                    "display_name": link.assignee.display_name,
                    "avatar_url": link.assignee.avatar_url,
                }
            )

        return Response(
            {
                "total_overdue": total_overdue,
                "total_urgent": total_urgent,
                "items": [
                    {
                        "id": str(row.id),
                        "name": row.name,
                        "sequence_id": row.sequence_id,
                        "priority": row.priority,
                        "target_date": row.target_date,
                        "days_overdue": (today - row.target_date).days if row.target_date and row.target_date < today else 0,
                        "state_group": row.state.group if row.state_id else None,
                        "assignees": assignees.get(row.id, []),
                    }
                    for row in rows
                ],
            }
        )
