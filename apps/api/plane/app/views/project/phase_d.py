# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Workflow transitions, worklogs and templates.

Three families in one module because they are three small CRUD surfaces over three new
tables, and splitting them into three files would spread one migration's worth of code
across the tree without making any of it easier to find.

The interesting behaviour is not here -- it is in `plane/utils/workflow.py`, which the issue
serializer consults, and in `Template.apply`, which resolves what it can and drops what it
cannot.
"""

# Django imports
from django.db.models import Sum

# Third party imports
from rest_framework import serializers, status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import ProjectEntityPermission, allow_permission, ROLE
from plane.app.serializers.base import BaseSerializer
from plane.app.views.base import BaseAPIView, BaseViewSet
from plane.db.models import (
    Automation,
    Issue,
    Project,
    StateTransition,
    StateTransitionApprover,
    Template,
    Worklog,
)


class StateTransitionSerializer(BaseSerializer):
    approver_ids = serializers.ListField(child=serializers.UUIDField(), required=False, write_only=True)
    approvers = serializers.SerializerMethodField()

    class Meta:
        model = StateTransition
        fields = "__all__"
        read_only_fields = ["workspace", "project"]

    def get_approvers(self, obj):
        return [str(approver.member_id) for approver in obj.approvers.all()]

    def validate(self, data):
        project_id = self.context.get("project_id")
        from_state = data.get("from_state", getattr(self.instance, "from_state", None))
        to_state = data.get("to_state", getattr(self.instance, "to_state", None))
        # Both ends have to be states of this project; an edge to another project's state
        # would be unreachable and would make the source state look constrained for nothing.
        for state in (from_state, to_state):
            if state and str(state.project_id) != str(project_id):
                raise serializers.ValidationError("Both states must belong to this project.")
        if from_state and to_state and from_state.id == to_state.id:
            raise serializers.ValidationError("A transition needs two different states.")
        return data


class WorklogSerializer(BaseSerializer):
    class Meta:
        model = Worklog
        fields = "__all__"
        read_only_fields = ["workspace", "project", "logged_by", "issue"]

    def validate_duration(self, value):
        if value <= 0:
            raise serializers.ValidationError("A worklog needs a duration greater than zero.")
        return value


class TemplateSerializer(BaseSerializer):
    class Meta:
        model = Template
        fields = "__all__"
        read_only_fields = ["workspace"]


class StateTransitionViewSet(BaseViewSet):
    """The project's workflow, as an allow-list of edges."""

    permission_classes = [ProjectEntityPermission]
    model = StateTransition
    serializer_class = StateTransitionSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["project_id"] = self.kwargs.get("project_id")
        return context

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(workspace__slug=self.kwargs.get("slug"), project_id=self.kwargs.get("project_id"))
            .select_related("from_state", "to_state")
            .prefetch_related("approvers")
        )

    def perform_create(self, serializer):
        approver_ids = serializer.validated_data.pop("approver_ids", [])
        transition = serializer.save(project_id=self.kwargs.get("project_id"))
        self._set_approvers(transition, approver_ids)

    def perform_update(self, serializer):
        approver_ids = serializer.validated_data.pop("approver_ids", None)
        transition = serializer.save()
        if approver_ids is not None:
            self._set_approvers(transition, approver_ids, replace=True)

    def _set_approvers(self, transition, approver_ids, replace=False):
        """Approvers are replaced rather than added to.

        Unlike labels on a bulk edit, an approver list is a complete statement of who may
        make this move -- adding to it would make removing somebody impossible through the
        same call that set them.
        """
        if replace:
            StateTransitionApprover.objects.filter(transition=transition).delete()
        StateTransitionApprover.objects.bulk_create(
            [
                StateTransitionApprover(
                    transition=transition,
                    member_id=member_id,
                    project_id=transition.project_id,
                    workspace_id=transition.workspace_id,
                )
                for member_id in approver_ids
            ],
            batch_size=100,
        )


class WorklogViewSet(BaseViewSet):
    """Time logged against one work item."""

    permission_classes = [ProjectEntityPermission]
    model = Worklog
    serializer_class = WorklogSerializer

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
                issue_id=self.kwargs.get("issue_id"),
            )
            .select_related("logged_by")
        )

    def create(self, request, slug, project_id, issue_id):
        # The flag shipped years before anything could be logged against it. It gates writes
        # rather than reads, so switching it off hides the control without losing history.
        if not Project.objects.filter(pk=project_id, is_time_tracking_enabled=True).exists():
            return Response(
                {"error": "Time tracking is not enabled for this project."}, status=status.HTTP_400_BAD_REQUEST
            )
        if not Issue.objects.filter(pk=issue_id, project_id=project_id).exists():
            return Response({"error": "The work item does not exist in this project."}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(project_id=project_id, issue_id=issue_id, logged_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class WorklogSummaryEndpoint(BaseAPIView):
    """Total minutes on a work item, and per person."""

    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id, issue_id):
        rows = (
            Worklog.objects.filter(workspace__slug=slug, project_id=project_id, issue_id=issue_id)
            .values("logged_by_id", "logged_by__display_name")
            .annotate(total=Sum("duration"))
        )
        by_member = [
            {
                "member_id": str(row["logged_by_id"]),
                "display_name": row["logged_by__display_name"],
                "duration": row["total"],
            }
            for row in rows
        ]
        return Response(
            {"duration": sum(row["duration"] for row in by_member), "by_member": by_member},
            status=status.HTTP_200_OK,
        )


class TemplateViewSet(BaseViewSet):
    """Saved shapes, workspace-scoped, filtered by kind."""

    model = Template
    serializer_class = TemplateSerializer

    def get_queryset(self):
        queryset = super().get_queryset().filter(workspace__slug=self.kwargs.get("slug"))
        kind = self.request.query_params.get("kind")
        return queryset.filter(kind=kind) if kind else queryset

    @allow_permission(allowed_roles=[ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def create(self, request, slug):
        workspace_id = (
            Project.objects.filter(workspace__slug=slug).values_list("workspace_id", flat=True).first()
        )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(workspace_id=workspace_id)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TemplateApplyEndpoint(BaseAPIView):
    """Create a work item from a template.

    The payload is resolved rather than trusted. A template outlives the schema it was
    written against, so a saved state or label that has since been deleted is dropped instead
    of raising -- the alternative is a template that becomes unusable the first time somebody
    tidies up a project, with no way to see what it was trying to do.
    """

    permission_classes = [ProjectEntityPermission]

    KEEP = ("name", "description_html", "priority", "estimate_point_id", "start_date", "target_date")

    def post(self, request, slug, project_id, template_id):
        template = Template.objects.filter(
            pk=template_id, workspace__slug=slug, kind=Template.Kind.WORK_ITEM
        ).first()
        if not template:
            return Response({"error": "The template does not exist."}, status=status.HTTP_404_NOT_FOUND)

        payload = template.payload if isinstance(template.payload, dict) else {}
        fields = {key: payload[key] for key in self.KEEP if payload.get(key) is not None}
        fields.update({key: value for key, value in request.data.items() if key in self.KEEP})
        if not fields.get("name"):
            return Response({"error": "The template has no name to create from."}, status=status.HTTP_400_BAD_REQUEST)

        project = Project.objects.get(pk=project_id)
        dropped = []

        state_id = request.data.get("state_id") or payload.get("state_id")
        if state_id:
            from plane.db.models import State

            if State.objects.filter(pk=state_id, project_id=project_id).exists():
                fields["state_id"] = state_id
            else:
                dropped.append("state_id")

        issue = Issue.objects.create(
            project=project, workspace=project.workspace, created_by=request.user, **fields
        )

        return Response(
            {"id": str(issue.id), "name": issue.name, "dropped": dropped},
            status=status.HTTP_201_CREATED,
        )


class AutomationSerializer(BaseSerializer):
    class Meta:
        model = Automation
        fields = "__all__"
        read_only_fields = ["workspace", "project"]

    def validate_actions(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Actions must be an object.")
        # The engine applies a fixed set. Accepting anything else would promise an
        # expressiveness that does not exist and fail silently at run time.
        unknown = set(value) - {"priority", "assignee_ids", "label_ids"}
        if unknown:
            raise serializers.ValidationError(f"Unsupported actions: {', '.join(sorted(unknown))}.")
        return value


class AutomationViewSet(BaseViewSet):
    permission_classes = [ProjectEntityPermission]
    model = Automation
    serializer_class = AutomationSerializer

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(workspace__slug=self.kwargs.get("slug"), project_id=self.kwargs.get("project_id"))
        )

    def perform_create(self, serializer):
        serializer.save(project_id=self.kwargs.get("project_id"))
