# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Filing into an intake from outside the workspace.

This covers the code half of intake-by-email. The other half is a mail route that POSTs here,
which is deployment rather than code -- so what is pinned is the contract that route has to
meet, and the token behaviour that makes exposing it safe.
"""

import pytest
from rest_framework import status

from plane.db.models import Intake, IntakeIngestToken, IntakeIssue, Issue, Project, ProjectMember

INGEST_URL = "/api/intake/ingest/"


@pytest.fixture
def intake_project(db, workspace, create_user):
    project = Project.objects.create(
        name="Inbound", identifier="INBD", workspace=workspace, created_by=create_user, intake_view=True
    )
    ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20, is_active=True)
    intake = Intake.objects.create(workspace=workspace, project=project, name="Triage", is_default=True)
    return {"project": project, "intake": intake}


def tokens_url(workspace, project, intake):
    return (
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/intakes/{intake.id}/ingest-tokens/"
    )


@pytest.mark.contract
@pytest.mark.django_db
class TestIntakeIngest:
    def _token(self, session_client, workspace, fixture):
        created = session_client.post(
            tokens_url(workspace, fixture["project"], fixture["intake"]),
            data={"label": "Support mailbox"},
            content_type="application/json",
        )
        assert created.status_code == status.HTTP_201_CREATED
        return created.json()

    def test_the_secret_is_readable_once_and_stored_hashed(self, session_client, workspace, intake_project):
        """Storing it readable would defeat hashing it."""
        body = self._token(session_client, workspace, intake_project)

        assert body["token"]
        stored = IntakeIngestToken.objects.get(pk=body["id"])
        assert stored.token_hash != body["token"]
        assert len(stored.token_hash) == 64

        listed = session_client.get(
            tokens_url(workspace, intake_project["project"], intake_project["intake"])
        ).json()
        assert "token" not in listed[0]

    def test_a_forwarded_message_becomes_a_pending_intake_item(
        self, api_client, session_client, workspace, intake_project
    ):
        token = self._token(session_client, workspace, intake_project)["token"]

        response = api_client.post(
            INGEST_URL,
            data={
                "subject": "Login page returns 500",
                "body_html": "<p>Since this morning.</p>",
                "from_email": "reporter@example.com",
            },
            format="json",
            HTTP_X_INTAKE_TOKEN=token,
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["source"] == "EMAIL"
        issue = Issue.objects.get(pk=response.json()["id"])
        assert issue.name == "Login page returns 500"
        link = IntakeIssue.objects.get(issue=issue)
        assert link.status == -2
        assert link.source_email == "reporter@example.com"

    def test_a_form_post_is_recorded_as_a_form(self, api_client, session_client, workspace, intake_project):
        """A triager reads the two differently, so the distinction lives in the data."""
        token = self._token(session_client, workspace, intake_project)["token"]

        response = api_client.post(
            INGEST_URL, data={"subject": "Feature request"}, format="json", HTTP_X_INTAKE_TOKEN=token
        )

        assert response.json()["source"] == "FORM"

    def test_no_token_and_a_wrong_token_are_both_refused(self, api_client, workspace, intake_project):
        without = api_client.post(INGEST_URL, data={"subject": "Anything"}, format="json")
        wrong = api_client.post(
            INGEST_URL, data={"subject": "Anything"}, format="json", HTTP_X_INTAKE_TOKEN="not-a-token"
        )

        assert without.status_code == status.HTTP_401_UNAUTHORIZED
        assert wrong.status_code == status.HTTP_401_UNAUTHORIZED
        assert not Issue.objects.filter(name="Anything").exists()

    def test_a_deactivated_token_stops_working(self, api_client, session_client, workspace, intake_project):
        body = self._token(session_client, workspace, intake_project)
        IntakeIngestToken.objects.filter(pk=body["id"]).update(is_active=False)

        response = api_client.post(
            INGEST_URL, data={"subject": "After revocation"}, format="json", HTTP_X_INTAKE_TOKEN=body["token"]
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_a_long_subject_is_truncated_rather_than_refused(
        self, api_client, session_client, workspace, intake_project
    ):
        """A long subject line is a formatting accident, not a reason to drop a report."""
        token = self._token(session_client, workspace, intake_project)["token"]

        response = api_client.post(
            INGEST_URL, data={"subject": "x" * 400}, format="json", HTTP_X_INTAKE_TOKEN=token
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert len(Issue.objects.get(pk=response.json()["id"]).name) == 255

    def test_a_message_with_no_subject_is_refused(self, api_client, session_client, workspace, intake_project):
        token = self._token(session_client, workspace, intake_project)["token"]

        response = api_client.post(INGEST_URL, data={"body": "orphaned"}, format="json", HTTP_X_INTAKE_TOKEN=token)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
