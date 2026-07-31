# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""What the epic progress donut is allowed to claim.

Every case here is one the endpoint gets wrong if the obvious implementation is used: count
the epic's direct children and be done. The distinction between "children" and "descendants"
and the exclusion of the epic itself are the whole of the logic, so they are the whole of
the suite.
"""

import datetime

import pytest
from rest_framework import status

from plane.db.models import Issue, Project, ProjectMember, State


@pytest.fixture
def epic_project(db, workspace, create_user):
    project = Project.objects.create(
        name="Epic Project",
        identifier="EPAN",
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
    return project


class EpicAnalyticsFixtures:
    def _url(self, workspace, project, epic_id):
        return f"/api/workspaces/{workspace.slug}/projects/{project.id}/epics/{epic_id}/analytics/"

    def _state(self, workspace, project, name, group):
        return State.objects.create(
            workspace=workspace, project=project, name=name, group=group, sequence=1000
        )

    def _issue(self, workspace, project, name, state=None, parent=None, target_date=None):
        return Issue.objects.create(
            workspace=workspace,
            project=project,
            name=name,
            state=state,
            parent=parent,
            target_date=target_date,
        )


@pytest.mark.contract
@pytest.mark.django_db
class TestEpicAnalytics(EpicAnalyticsFixtures):
    def test_counts_every_depth_not_just_direct_children(self, session_client, workspace, epic_project):
        """An epic's children are features; the stories underneath carry the real progress.

        Counting one level reports this epic as entirely unstarted while both of its stories
        are done.
        """
        unstarted = self._state(workspace, epic_project, "Todo", "unstarted")
        completed = self._state(workspace, epic_project, "Done", "completed")

        epic = self._issue(workspace, epic_project, "Epic", state=unstarted)
        feature = self._issue(workspace, epic_project, "Feature", state=unstarted, parent=epic)
        self._issue(workspace, epic_project, "Story A", state=completed, parent=feature)
        self._issue(workspace, epic_project, "Story B", state=completed, parent=feature)

        response = session_client.get(self._url(workspace, epic_project, epic.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["completed_issues"] == 2
        # the feature, not the epic
        assert response.json()["unstarted_issues"] == 1

    def test_excludes_the_epic_itself(self, session_client, workspace, epic_project):
        """The epic summarises its own subtree, so counting it states one fact twice."""
        started = self._state(workspace, epic_project, "In Progress", "started")

        epic = self._issue(workspace, epic_project, "Epic", state=started)
        self._issue(workspace, epic_project, "Story", state=started, parent=epic)

        response = session_client.get(self._url(workspace, epic_project, epic.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["started_issues"] == 1

    def test_overdue_counts_only_open_work(self, session_client, workspace, epic_project):
        """A delivered item with a past target date was finished, not missed.

        Counting it overdue would paint a completed epic red, which is the failure mode that
        makes a progress widget stop being trusted.
        """
        started = self._state(workspace, epic_project, "In Progress", "started")
        completed = self._state(workspace, epic_project, "Done", "completed")
        cancelled = self._state(workspace, epic_project, "Cancelled", "cancelled")
        past = datetime.date.today() - datetime.timedelta(days=7)

        epic = self._issue(workspace, epic_project, "Epic", state=started)
        self._issue(workspace, epic_project, "Late", state=started, parent=epic, target_date=past)
        self._issue(workspace, epic_project, "Shipped", state=completed, parent=epic, target_date=past)
        self._issue(workspace, epic_project, "Dropped", state=cancelled, parent=epic, target_date=past)

        response = session_client.get(self._url(workspace, epic_project, epic.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["overdue_issues"] == 1

    def test_leaf_epic_reports_zeroes_rather_than_failing(self, session_client, workspace, epic_project):
        """A freshly created epic has nothing beneath it, which is a number, not an error."""
        started = self._state(workspace, epic_project, "In Progress", "started")
        epic = self._issue(workspace, epic_project, "Empty epic", state=started)

        response = session_client.get(self._url(workspace, epic_project, epic.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "backlog_issues": 0,
            "unstarted_issues": 0,
            "started_issues": 0,
            "completed_issues": 0,
            "cancelled_issues": 0,
            "overdue_issues": 0,
        }

    def test_sibling_subtrees_do_not_leak_in(self, session_client, workspace, epic_project):
        """Scoping is by descent, not by project. A second epic's work is not this one's."""
        started = self._state(workspace, epic_project, "In Progress", "started")

        epic = self._issue(workspace, epic_project, "Epic", state=started)
        self._issue(workspace, epic_project, "Mine", state=started, parent=epic)
        other = self._issue(workspace, epic_project, "Other epic", state=started)
        self._issue(workspace, epic_project, "Theirs", state=started, parent=other)

        response = session_client.get(self._url(workspace, epic_project, epic.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["started_issues"] == 1

    def test_unknown_epic_is_a_404(self, session_client, workspace, epic_project):
        response = session_client.get(
            self._url(workspace, epic_project, "00000000-0000-0000-0000-000000000000")
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_non_member_is_refused(self, client, workspace, epic_project):
        started = self._state(workspace, epic_project, "In Progress", "started")
        epic = self._issue(workspace, epic_project, "Epic", state=started)

        response = client.get(self._url(workspace, epic_project, epic.id))

        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
