# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The browser can read back the classification it is allowed to write.

The create serializer on the app tree takes `__all__`, so the browser could always send
`requirement_kind`; the read serializers listed their fields explicitly and did not include it.
The result was a field the UI could set and never see -- which is why nothing in the UI set it,
and why every work item on this instance still carries the default.

`milestone_id` was the same omission found the same way, and its comment in the serializer
records it. These tests pin the read side so the pair cannot drift apart again.
"""

import pytest
from rest_framework import status

from plane.db.models import Issue, Project, ProjectMember, State


@pytest.fixture
def classified_issue(db, workspace, create_user):
    project = Project.objects.create(
        name="Visible Project", identifier="VIS", workspace=workspace, created_by=create_user
    )
    ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20, is_active=True)
    state = State.objects.create(
        name="In progress",
        color="#F59E0B",
        group="started",
        sequence=15000,
        project=project,
        workspace=workspace,
        created_by=create_user,
        default=True,
    )
    issue = Issue.objects.create(
        name="Checkout P95 under 2s at peak",
        project=project,
        workspace=workspace,
        state=state,
        requirement_kind="quality",
        created_by=create_user,
    )
    return {"project": project, "issue": issue}


@pytest.mark.contract
@pytest.mark.django_db
class TestRequirementKindIsVisibleToTheBrowser:
    def test_the_list_carries_the_classification(self, session_client, workspace, classified_issue):
        response = session_client.get(
            f"/api/workspaces/{workspace.slug}/projects/{classified_issue['project'].id}/issues/"
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        rows = payload["results"] if isinstance(payload, dict) and "results" in payload else payload
        assert [row["requirement_kind"] for row in rows] == ["quality"]

    def test_the_detail_carries_the_classification(self, session_client, workspace, classified_issue):
        project_id = classified_issue["project"].id
        issue_id = classified_issue["issue"].id

        response = session_client.get(f"/api/workspaces/{workspace.slug}/projects/{project_id}/issues/{issue_id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["requirement_kind"] == "quality"

    def test_the_browser_can_reclassify_and_read_the_result_back(self, session_client, workspace, classified_issue):
        """Write then read, because the bug was that only one of the two worked."""
        project_id = classified_issue["project"].id
        issue_id = classified_issue["issue"].id

        patched = session_client.patch(
            f"/api/workspaces/{workspace.slug}/projects/{project_id}/issues/{issue_id}/",
            data={"requirement_kind": "functional"},
            content_type="application/json",
        )
        # 204: this endpoint acknowledges the write without echoing the work item back, which
        # is exactly why the read side had to be fixed separately.
        assert patched.status_code == status.HTTP_204_NO_CONTENT

        reread = session_client.get(f"/api/workspaces/{workspace.slug}/projects/{project_id}/issues/{issue_id}/")
        assert reread.json()["requirement_kind"] == "functional"
