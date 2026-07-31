# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Filing into an intake from outside the workspace.

This is the code half of intake-by-email. The other half is deployment: something has to
receive mail for an address and POST it here -- an MX record and a forwarding service, or a
mail hook from whatever already handles the domain. No amount of code in this repository
makes a message arrive, which is why this takes an already-parsed payload rather than
pretending to be a mail server.

The same endpoint serves public forms. A form post and a forwarded email differ only in which
`source` is recorded, and a triager wants to know which, so the distinction is kept in the
data and nowhere else.

Authentication is a bearer token scoped to one intake, stored hashed. Anything holding the
token can file work items, which makes it a credential; a table of readable credentials is
the kind of thing that ends up in a support-ticket screenshot.
"""

# Python imports
import hashlib
import secrets

# Django imports
from django.db import transaction
from django.utils import timezone

# Third party imports
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

# Module imports
from plane.app.permissions import ProjectEntityPermission
from plane.app.serializers.base import BaseSerializer
from plane.app.views.base import BaseAPIView, BaseViewSet
from plane.db.models import Intake, IntakeIngestToken, IntakeIssue, Issue, State
from plane.utils.content_validator import validate_html_content

MAX_NAME = 255


def hash_token(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


class IntakeIngestTokenSerializer(BaseSerializer):
    class Meta:
        model = IntakeIngestToken
        fields = ["id", "label", "is_active", "last_used_at", "created_at", "intake"]
        read_only_fields = ["last_used_at", "created_at", "intake"]


class IntakeIngestTokenViewSet(BaseViewSet):
    """Manage the tokens that back an intake's mail address or public form."""

    permission_classes = [ProjectEntityPermission]
    model = IntakeIngestToken
    serializer_class = IntakeIngestTokenSerializer

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
                intake_id=self.kwargs.get("intake_id"),
            )
        )

    def create(self, request, slug, project_id, intake_id):
        intake = Intake.objects.filter(pk=intake_id, project_id=project_id, workspace__slug=slug).first()
        if not intake:
            return Response({"error": "The intake does not exist."}, status=status.HTTP_404_NOT_FOUND)

        raw = secrets.token_urlsafe(32)
        token = IntakeIngestToken.objects.create(
            intake=intake,
            project_id=project_id,
            label=request.data.get("label") or "Ingest token",
            token_hash=hash_token(raw),
        )
        # The only time the secret is readable. Storing it would defeat hashing it.
        return Response(
            {**IntakeIngestTokenSerializer(token).data, "token": raw},
            status=status.HTTP_201_CREATED,
        )


class IntakeIngestEndpoint(BaseAPIView):
    """Accept a parsed message and file it as a pending intake item.

    Unauthenticated by session on purpose -- the caller is a mail forwarder or a public form,
    neither of which has a Plane login. The bearer token is the whole of the authorisation,
    which is why it is scoped to one intake and revocable on its own.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        provided = request.headers.get("X-Intake-Token") or ""
        if not provided:
            return Response({"error": "An intake token is required."}, status=status.HTTP_401_UNAUTHORIZED)

        token = (
            IntakeIngestToken.objects.filter(token_hash=hash_token(provided), is_active=True)
            .select_related("intake", "project", "workspace")
            .first()
        )
        if not token:
            return Response({"error": "The intake token is not valid."}, status=status.HTTP_401_UNAUTHORIZED)

        name = (request.data.get("subject") or request.data.get("name") or "").strip()
        if not name:
            return Response({"error": "A subject is required."}, status=status.HTTP_400_BAD_REQUEST)
        # Truncated rather than refused: a long subject line is a formatting accident, not a
        # reason to drop somebody's report on the floor.
        name = name[:MAX_NAME]

        body = request.data.get("body_html") or request.data.get("body") or ""
        is_valid, _error, sanitized = validate_html_content(str(body))
        description_html = sanitized if sanitized is not None else ""
        if not is_valid:
            description_html = ""

        source = "EMAIL" if request.data.get("from_email") else "FORM"
        default_state = (
            State.objects.filter(project=token.project, group="triage").first()
            or State.objects.filter(project=token.project, default=True).first()
        )

        with transaction.atomic():
            issue = Issue.objects.create(
                project=token.project,
                workspace=token.workspace,
                name=name,
                description_html=description_html,
                state=default_state,
            )
            IntakeIssue.objects.create(
                intake=token.intake,
                issue=issue,
                project=token.project,
                workspace=token.workspace,
                source=source,
                source_email=request.data.get("from_email"),
            )
            IntakeIngestToken.objects.filter(pk=token.pk).update(last_used_at=timezone.now())

        return Response({"id": str(issue.id), "source": source}, status=status.HTTP_201_CREATED)
