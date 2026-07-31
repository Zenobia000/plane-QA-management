# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The cycle analytics endpoint the Active Cycle widget reads.

It returned 500 for every request and nothing noticed, because nothing asked. The
assignee annotation builds an avatar URL with `Concat(Value(str), <uuid column>, Value(str))`
and Django resolves an expression's output field from its arguments, so a CharField mixed
with a UUIDField raises at query-compile time -- before a single row is touched. The outer
`Case` sets `output_field`; the inner `Concat` did not.

The panel that consumes this renders an empty state when the distribution is missing, so
the failure looked like "no burndown chart" rather than an error.
"""

import pytest
from rest_framework import status

from plane.db.models import Cycle, Issue, IssueAssignee, Project, ProjectMember, State


@pytest.fixture
def project(db, workspace, create_user):
    created = Project.objects.create(
        name="Analytics", identifier="ANLY", workspace=workspace, created_by=create_user
    )
    ProjectMember.objects.create(
        workspace=workspace, project=created, member=create_user, role=20, is_active=True
    )
    return created


@pytest.fixture
def cycle_with_assigned_work(db, workspace, project, create_user):
    """An assignee is what triggers the annotation; without one the bug stays hidden."""
    from django.utils import timezone
    from datetime import timedelta

    today = timezone.now()
    cycle = Cycle.objects.create(
        workspace=workspace,
        project=project,
        name="Sprint",
        start_date=today - timedelta(days=5),
        end_date=today + timedelta(days=5),
        owned_by=create_user,
    )
    done = State.objects.create(
        workspace=workspace, project=project, name="Done", group="completed", sequence=1000
    )
    for index in range(2):
        issue = Issue.objects.create(
            workspace=workspace, project=project, name=f"Item {index}", state=done, created_by=create_user
        )
        IssueAssignee.objects.create(
            workspace=workspace, project=project, issue=issue, assignee=create_user, created_by=create_user
        )
        cycle.issue_cycle.create(workspace=workspace, project=project, issue=issue, created_by=create_user)
    return cycle


def analytics_url(workspace, project, cycle, kind="issues"):
    return (
        f"/api/workspaces/{workspace.slug}/projects/{project.id}"
        f"/cycles/{cycle.id}/analytics/?type={kind}"
    )


@pytest.mark.contract
@pytest.mark.django_db
class TestCycleAnalytics:
    def test_the_issue_distribution_is_served(
        self, session_client, workspace, project, cycle_with_assigned_work
    ):
        response = session_client.get(analytics_url(workspace, project, cycle_with_assigned_work))

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert set(body) == {"assignees", "labels", "completion_chart"}

    def test_an_assignee_carries_a_usable_avatar_url(
        self, session_client, workspace, project, cycle_with_assigned_work
    ):
        """The annotation this asserts is the one that used to raise FieldError."""
        body = session_client.get(analytics_url(workspace, project, cycle_with_assigned_work)).json()

        assert body["assignees"], "an assigned cycle should report its assignees"
        assignee = body["assignees"][0]
        assert "avatar_url" in assignee
        assert assignee["display_name"]

    def test_the_points_distribution_is_served_too(
        self, session_client, workspace, project, cycle_with_assigned_work
    ):
        """Both branches build the same avatar annotation, so both could raise."""
        response = session_client.get(
            analytics_url(workspace, project, cycle_with_assigned_work, kind="points")
        )

        assert response.status_code == status.HTTP_200_OK
        assert "completion_chart" in response.json()

    def test_the_completion_chart_spans_the_cycle(
        self, session_client, workspace, project, cycle_with_assigned_work
    ):
        chart = session_client.get(analytics_url(workspace, project, cycle_with_assigned_work)).json()[
            "completion_chart"
        ]

        assert len(chart) == 11  # start and end inclusive
        # Dates past today carry no reading rather than reporting the work as delivered.
        assert any(value is None for value in chart.values())
