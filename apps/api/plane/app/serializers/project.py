# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third party imports
from rest_framework import serializers

# Python imports
import re

# Module imports
from .base import BaseSerializer, DynamicBaseSerializer
from django.db.models import Max
from plane.app.serializers.workspace import WorkspaceLiteSerializer
from plane.app.serializers.user import UserLiteSerializer, UserAdminLiteSerializer
from plane.db.models import (
    EntityUpdate,
    Issue,
    Label,
    Milestone,
    Project,
    ProjectLink,
    ProjectMember,
    ProjectMemberInvite,
    ProjectIdentifier,
    DeployBoard,
    ProjectPublicMember,
    IssueSequence,
)
from plane.utils.content_validator import (
    validate_html_content,
)


class ProjectSerializer(BaseSerializer):
    workspace_detail = WorkspaceLiteSerializer(source="workspace", read_only=True)
    inbox_view = serializers.BooleanField(read_only=True, source="intake_view")

    class Meta:
        model = Project
        fields = "__all__"
        read_only_fields = ["workspace", "deleted_at"]

    def validate_name(self, name):
        project_id = self.instance.id if self.instance else None
        workspace_id = self.context["workspace_id"]

        if re.match(Project.FORBIDDEN_IDENTIFIER_CHARS_PATTERN, name):
            raise serializers.ValidationError(detail="PROJECT_NAME_CANNOT_CONTAIN_SPECIAL_CHARACTERS")

        project = Project.objects.filter(name=name, workspace_id=workspace_id)

        if project_id:
            project = project.exclude(id=project_id)

        if project.exists():
            raise serializers.ValidationError(
                detail="PROJECT_NAME_ALREADY_EXIST",
            )

        return name

    def validate_identifier(self, identifier):
        project_id = self.instance.id if self.instance else None
        workspace_id = self.context["workspace_id"]

        if re.match(Project.FORBIDDEN_IDENTIFIER_CHARS_PATTERN, identifier):
            raise serializers.ValidationError(detail="PROJECT_IDENTIFIER_CANNOT_CONTAIN_SPECIAL_CHARACTERS")

        project = Project.objects.filter(identifier=identifier, workspace_id=workspace_id)

        if project_id:
            project = project.exclude(id=project_id)

        if project.exists():
            raise serializers.ValidationError(
                detail="PROJECT_IDENTIFIER_ALREADY_EXIST",
            )

        return identifier

    def validate(self, data):
        # Validate description content for security
        if "description_html" in data and data["description_html"]:
            is_valid, error_msg, sanitized_html = validate_html_content(str(data["description_html"]))
            # Update the data with sanitized HTML if available
            if sanitized_html is not None:
                data["description_html"] = sanitized_html

            if not is_valid:
                raise serializers.ValidationError({"error": "html content is not valid"})

        return data

    def create(self, validated_data):
        workspace_id = self.context["workspace_id"]

        project = Project.objects.create(**validated_data, workspace_id=workspace_id)

        ProjectIdentifier.objects.create(name=project.identifier, project=project, workspace_id=workspace_id)

        return project


class ProjectLiteSerializer(BaseSerializer):
    class Meta:
        model = Project
        fields = [
            "id",
            "identifier",
            "name",
            "cover_image",
            "cover_image_url",
            "logo_props",
            "description",
        ]
        read_only_fields = fields


class ProjectListSerializer(DynamicBaseSerializer):
    is_favorite = serializers.BooleanField(read_only=True)
    sort_order = serializers.FloatField(read_only=True)
    member_role = serializers.IntegerField(read_only=True)
    anchor = serializers.CharField(read_only=True)
    members = serializers.SerializerMethodField()
    cover_image_url = serializers.CharField(read_only=True)
    inbox_view = serializers.BooleanField(read_only=True, source="intake_view")
    next_work_item_sequence = serializers.SerializerMethodField()

    def get_members(self, obj):
        project_members = getattr(obj, "members_list", None)
        if project_members is not None:
            # Filter members by the project ID
            return [member.member_id for member in project_members if member.is_active and not member.member.is_bot]
        return []

    def get_next_work_item_sequence(self, obj):
        """Get the next sequence ID that will be assigned to a new issue"""
        max_sequence = IssueSequence.objects.filter(project_id=obj.id).aggregate(max_seq=Max("sequence"))["max_seq"]
        return (max_sequence + 1) if max_sequence else 1

    class Meta:
        model = Project
        fields = "__all__"


class ProjectDetailSerializer(BaseSerializer):
    # workspace = WorkSpaceSerializer(read_only=True)
    default_assignee = UserLiteSerializer(read_only=True)
    project_lead = UserLiteSerializer(read_only=True)
    is_favorite = serializers.BooleanField(read_only=True)
    sort_order = serializers.FloatField(read_only=True)
    member_role = serializers.IntegerField(read_only=True)
    anchor = serializers.CharField(read_only=True)

    class Meta:
        model = Project
        fields = "__all__"


class ProjectMemberSerializer(BaseSerializer):
    workspace = WorkspaceLiteSerializer(read_only=True)
    project = ProjectLiteSerializer(read_only=True)
    member = UserLiteSerializer(read_only=True)

    class Meta:
        model = ProjectMember
        fields = "__all__"


class ProjectMemberPreferenceSerializer(BaseSerializer):
    class Meta:
        model = ProjectMember
        fields = ["preferences", "project_id", "member_id", "workspace_id"]

    def validate_preferences(self, value):
        preferences = self.instance.preferences

        preferences.update(value)
        return preferences


class ProjectMemberAdminSerializer(BaseSerializer):
    workspace = WorkspaceLiteSerializer(read_only=True)
    project = ProjectLiteSerializer(read_only=True)
    member = UserAdminLiteSerializer(read_only=True)

    class Meta:
        model = ProjectMember
        fields = "__all__"


class ProjectMemberRoleSerializer(DynamicBaseSerializer):
    original_role = serializers.IntegerField(source="role", read_only=True)

    class Meta:
        model = ProjectMember
        fields = ("id", "role", "member", "project", "original_role", "created_at")
        read_only_fields = ["original_role", "created_at"]


class ProjectMemberInviteSerializer(BaseSerializer):
    project = ProjectLiteSerializer(read_only=True)
    workspace = WorkspaceLiteSerializer(read_only=True)

    class Meta:
        model = ProjectMemberInvite
        fields = "__all__"


class ProjectMemberInvitePublicSerializer(BaseSerializer):
    """Safe read-only serializer for the public project invite GET endpoint.

    Intentionally excludes ``email`` and ``token`` so that an unauthenticated
    caller cannot retrieve the invitee's email address or the acceptance token
    (GHSA-2r58-hgv7-635q).
    """

    project = ProjectLiteSerializer(read_only=True)
    workspace = WorkspaceLiteSerializer(read_only=True)

    class Meta:
        model = ProjectMemberInvite
        fields = [
            "id",
            "project",
            "workspace",
            "role",
            "message",
            "accepted",
            "responded_at",
        ]
        read_only_fields = fields


class ProjectIdentifierSerializer(BaseSerializer):
    class Meta:
        model = ProjectIdentifier
        fields = "__all__"


class ProjectMemberLiteSerializer(BaseSerializer):
    member = UserLiteSerializer(read_only=True)
    is_subscribed = serializers.BooleanField(read_only=True)

    class Meta:
        model = ProjectMember
        fields = ["member", "id", "is_subscribed"]
        read_only_fields = fields


class DeployBoardSerializer(BaseSerializer):
    project_details = ProjectLiteSerializer(read_only=True, source="project")
    workspace_detail = WorkspaceLiteSerializer(read_only=True, source="workspace")

    class Meta:
        model = DeployBoard
        fields = "__all__"
        read_only_fields = ["workspace", "project", "anchor"]


class ProjectPublicMemberSerializer(BaseSerializer):
    class Meta:
        model = ProjectPublicMember
        fields = "__all__"
        read_only_fields = ["workspace", "project", "member"]


class ProjectLinkSerializer(BaseSerializer):
    class Meta:
        model = ProjectLink
        fields = "__all__"
        read_only_fields = ["workspace", "project", "created_by", "updated_by", "created_at", "updated_at"]

    def to_internal_value(self, data):
        # Same leniency `ModuleLinkSerializer` applies, so a link pasted without a scheme
        # behaves the same wherever it is pasted.
        url = data.get("url", "")
        if url and not url.startswith(("http://", "https://")):
            data["url"] = "http://" + url

        return super().to_internal_value(data)


class MilestoneSerializer(BaseSerializer):
    """A milestone as the web app writes it.

    The token API has carried milestones since they were added, but nothing on this side
    did, so the browser could display them and not change them. Same fields and the same
    empty-name rule as `plane.api.serializers.portfolio.MilestoneSerializer` -- one shape,
    two authentication surfaces.

    `work_item_count` rides along because the delete rule depends on it: a milestone with
    work items cannot be removed, and a UI that only learns that from a rejected request
    offers an action it knows will fail.
    """

    work_item_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Milestone
        fields = [
            "id",
            "name",
            "description",
            "target_date",
            "status",
            "sort_order",
            "work_item_count",
            "project",
            "workspace",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "project", "workspace", "created_at", "updated_at"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name cannot be empty.")
        return value


class EntityUpdateSerializer(BaseSerializer):
    actor_detail = UserLiteSerializer(source="actor", read_only=True)
    reply_count = serializers.IntegerField(read_only=True)
    label_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    # `updated_at` moves on its own for reasons a reader does not care about, so the client
    # is told plainly whether the text was rewritten after it was published. An announcement
    # edited silently is worse than one that cannot be edited at all.
    is_edited = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = EntityUpdate
        fields = "__all__"
        read_only_fields = ["workspace", "project", "actor", "created_by", "updated_by", "created_at", "updated_at"]

    def get_is_edited(self, obj) -> bool:
        return bool(obj.edited_at)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["label_ids"] = [str(link.label_id) for link in instance.labels.all()]
        return data

    def validate_label_ids(self, value):
        """Topics have to belong to this project; the join table cannot enforce it."""
        project_id = self.context.get("project_id")
        known = set(
            Label.objects.filter(project_id=project_id, id__in=value).values_list("id", flat=True)
        )
        unknown = [str(label_id) for label_id in value if label_id not in known]
        if unknown:
            raise serializers.ValidationError(f"Labels not in this project: {', '.join(unknown)}")
        return value

    def validate(self, data):
        """Resolve the target inside the request's project before anything is written.

        The model keys its target by `entity_name` plus a bare UUID, which buys one table
        for two entities and costs referential integrity. That cost is paid here: without
        this check an update could be filed against another project's work item, and the
        database would happily store it.
        """
        project_id = self.context.get("project_id")
        entity_name = data.get("entity_name", getattr(self.instance, "entity_name", None))
        entity_identifier = data.get("entity_identifier", getattr(self.instance, "entity_identifier", None))

        if entity_name == EntityUpdate.EntityName.PROJECT:
            if str(entity_identifier) != str(project_id):
                raise serializers.ValidationError("A project update must name the project it belongs to.")
        elif entity_name == EntityUpdate.EntityName.WORK_ITEM:
            if not Issue.objects.filter(pk=entity_identifier, project_id=project_id).exists():
                raise serializers.ValidationError("The work item does not exist in this project.")

        parent = data.get("parent")
        if parent and parent.project_id != project_id:
            raise serializers.ValidationError("A reply has to belong to the same project as the update.")

        return data
