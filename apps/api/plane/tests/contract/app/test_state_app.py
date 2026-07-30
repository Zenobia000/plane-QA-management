# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Who may reshape a project's workflow.

Editing a state is not a cosmetic act. Renaming one renames a board column for every
member, and moving one between groups changes what the release gate treats as an unresolved
defect and what coverage treats as owing an acceptance contract. `create`, `destroy` and
`mark_as_default` were always ADMIN-only and the settings screen has always been gated on
ADMIN; `partial_update` alone admitted GUEST.
"""

import pytest
from rest_framework import status

from plane.db.models import Project, ProjectMember, State, User, WorkspaceMember


def state_url(slug, project_id, pk=None):
    base = f"/api/workspaces/{slug}/projects/{project_id}/states/"
    return f"{base}{pk}/" if pk else base


@pytest.fixture
def project_with_states(db, workspace, create_user):
    project = Project.objects.create(
        name="Workflow Project",
        identifier="WFP",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(
        workspace=workspace,
        project=project,
        member=create_user,
        role=20,
        is_active=True,
    )
    State.objects.create(
        name="In Diversity Testing",
        color="#8B5CF6",
        group="started",
        sequence=15000,
        project=project,
        workspace=workspace,
        created_by=create_user,
    )
    return project


def _join_as_guest(client, workspace, project):
    guest = User.objects.create_user(email="guest-state@example.com", username="gueststate")
    WorkspaceMember.objects.create(workspace=workspace, member=guest, role=5, is_active=True)
    ProjectMember.objects.create(workspace=workspace, project=project, member=guest, role=5, is_active=True)
    client.force_authenticate(user=guest)
    return guest


@pytest.mark.contract
@pytest.mark.django_db
class TestStatePartialUpdatePermissions:
    def test_admin_can_rename_a_state(self, session_client, workspace, project_with_states):
        state = project_with_states.project_state.get(name="In Diversity Testing")

        response = session_client.patch(
            state_url(workspace.slug, project_with_states.id, state.id),
            {"name": "In QA Testing"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        state.refresh_from_db()
        assert state.name == "In QA Testing"

    def test_guest_cannot_rename_a_state(self, session_client, workspace, project_with_states):
        state = project_with_states.project_state.get(name="In Diversity Testing")
        _join_as_guest(session_client, workspace, project_with_states)

        response = session_client.patch(
            state_url(workspace.slug, project_with_states.id, state.id),
            {"name": "Whatever"},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        state.refresh_from_db()
        assert state.name == "In Diversity Testing"

    def test_guest_cannot_move_a_state_between_groups(self, session_client, workspace, project_with_states):
        """The consequential edit: regrouping changes gate and coverage semantics.

        Dragging a state into `completed` would make defects sitting in it stop blocking
        the release gate, which is a decision no guest should be able to make.
        """
        state = project_with_states.project_state.get(name="In Diversity Testing")
        _join_as_guest(session_client, workspace, project_with_states)

        response = session_client.patch(
            state_url(workspace.slug, project_with_states.id, state.id),
            {"group": "completed"},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        state.refresh_from_db()
        assert state.group == "started"

    def test_guest_can_still_list_states(self, session_client, workspace, project_with_states):
        """Reading the workflow stays open -- a guest has to see the board."""
        _join_as_guest(session_client, workspace, project_with_states)

        response = session_client.get(state_url(workspace.slug, project_with_states.id))

        assert response.status_code == status.HTTP_200_OK
