# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Dashboards, and the aggregate each widget asks for.

The case that matters is scope: a widget stores which projects it counts, and the endpoint
intersects that with the reader's own memberships. A widget that could count projects the
reader cannot open would report totals they have no way to reconcile.
"""

import pytest
from rest_framework import status

from plane.db.models import Dashboard, DashboardWidget, Issue, Project, ProjectMember, State


@pytest.fixture
def board(db, workspace, create_user):
    joined = Project.objects.create(
        name="Joined", identifier="JOIN", workspace=workspace, created_by=create_user
    )
    ProjectMember.objects.create(workspace=workspace, project=joined, member=create_user, role=20, is_active=True)
    # Deliberately no membership row: the reader cannot open this one.
    unjoined = Project.objects.create(
        name="Unjoined", identifier="UNJN", workspace=workspace, created_by=create_user
    )
    dashboard = Dashboard.objects.create(workspace=workspace, name="Delivery", owned_by=create_user)
    return {"joined": joined, "unjoined": unjoined, "dashboard": dashboard}


def dashboards_url(workspace):
    return f"/api/workspaces/{workspace.slug}/dashboards/"


def data_url(workspace, dashboard, widget):
    return f"{dashboards_url(workspace)}{dashboard.id}/widgets/{widget.id}/data/"


@pytest.mark.contract
@pytest.mark.django_db
class TestDashboards:
    def test_a_dashboard_and_a_widget_are_created(self, session_client, workspace, board):
        created = session_client.post(
            dashboards_url(workspace), data={"name": "Ops"}, content_type="application/json"
        )
        assert created.status_code == status.HTTP_201_CREATED

        widget = session_client.post(
            f"{dashboards_url(workspace)}{created.json()['id']}/widgets/",
            data={"name": "By state", "group_by": "state_group", "chart": "bar"},
            content_type="application/json",
        )
        assert widget.status_code == status.HTTP_201_CREATED

    def test_a_widget_groups_work_items_by_state_group(self, session_client, workspace, board):
        project = board["joined"]
        done = State.objects.create(
            workspace=workspace, project=project, name="Done", group="completed", sequence=1000
        )
        todo = State.objects.create(
            workspace=workspace, project=project, name="Todo", group="unstarted", sequence=2000
        )
        Issue.objects.create(workspace=workspace, project=project, name="A", state=done)
        Issue.objects.create(workspace=workspace, project=project, name="B", state=todo)
        Issue.objects.create(workspace=workspace, project=project, name="C", state=todo)

        widget = DashboardWidget.objects.create(
            dashboard=board["dashboard"], workspace=workspace, name="By state", group_by="state_group"
        )
        body = session_client.get(data_url(workspace, board["dashboard"], widget)).json()

        assert body["total"] == 3
        assert {row["key"]: row["count"] for row in body["series"]} == {"unstarted": 2, "completed": 1}

    def test_a_widget_cannot_count_projects_the_reader_cannot_open(
        self, session_client, workspace, board
    ):
        """Scope is intersected with the caller's memberships, not trusted from the widget."""
        Issue.objects.create(workspace=workspace, project=board["unjoined"], name="Hidden")
        Issue.objects.create(workspace=workspace, project=board["joined"], name="Visible")

        widget = DashboardWidget.objects.create(
            dashboard=board["dashboard"],
            workspace=workspace,
            name="Everything",
            group_by="project",
            project_ids=[str(board["joined"].id), str(board["unjoined"].id)],
        )
        body = session_client.get(data_url(workspace, board["dashboard"], widget)).json()

        assert body["total"] == 1
        assert [row["label"] for row in body["series"]] == ["Joined"]

    def test_an_empty_scope_means_every_project_the_reader_is_in(self, session_client, workspace, board):
        Issue.objects.create(workspace=workspace, project=board["unjoined"], name="Hidden")
        Issue.objects.create(workspace=workspace, project=board["joined"], name="Visible")

        widget = DashboardWidget.objects.create(
            dashboard=board["dashboard"], workspace=workspace, name="Mine", group_by="project", project_ids=[]
        )
        body = session_client.get(data_url(workspace, board["dashboard"], widget)).json()

        assert body["total"] == 1

    def test_a_private_dashboard_is_hidden_from_others(self, session_client, workspace, board, django_user_model):
        other = django_user_model.objects.create(
            email="other@example.com", username="other", display_name="Other"
        )
        Dashboard.objects.create(workspace=workspace, name="Theirs", owned_by=other, access=0)

        names = [row["name"] for row in session_client.get(dashboards_url(workspace)).json()]

        assert "Theirs" not in names
        assert "Delivery" in names
