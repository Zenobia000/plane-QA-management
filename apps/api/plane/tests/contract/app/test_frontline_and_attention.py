# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The two panels that say who is unhappy and what breaks first.

Both are read-only derivations, and both exist because the overview used to report totals
that nobody could act on. What is pinned here is the grouping and the ordering -- the
arithmetic is trivial, the judgement about which row goes at the top is not.

Nothing in this file names a category. The whole point of the frontline endpoint is that
the project decides what it groups by, so the fixtures invent their own vocabulary and the
endpoint is never told what the words mean.
"""

import pytest
from django.utils import timezone

from plane.db.models import (
    Intake,
    IntakeIssue,
    Issue,
    IssueAssignee,
    Project,
    ProjectMember,
    State,
    WorkItemProperty,
    WorkItemPropertyOption,
    WorkItemPropertyValue,
)


@pytest.fixture
def project(db, workspace, create_user):
    created = Project.objects.create(
        name="Frontline", identifier="FRNT", workspace=workspace, created_by=create_user
    )
    ProjectMember.objects.create(
        workspace=workspace, project=created, member=create_user, role=20, is_active=True
    )
    return created


@pytest.fixture
def states(db, workspace, project):
    return {
        group: State.objects.create(
            workspace=workspace, project=project, name=group.title(), group=group, sequence=index * 1000
        )
        for index, group in enumerate(("unstarted", "started", "completed"))
    }


@pytest.fixture
def dimension(db, workspace, project):
    """A project's own grouping vocabulary. The endpoint never sees these names in code."""
    prop = WorkItemProperty.objects.create(
        workspace=workspace,
        project=project,
        name="合作單位",
        kind=WorkItemProperty.Kind.MULTI_SELECT,
        is_grouping_dimension=True,
    )
    for index, (value, label) in enumerate((("acme", "Acme 工業"), ("globex", "Globex"))):
        WorkItemPropertyOption.objects.create(
            workspace=workspace, project=project, property=prop, value=value, label=label, sort_order=index
        )
    return prop


@pytest.fixture
def intake(db, workspace, project, create_user):
    return Intake.objects.create(workspace=workspace, project=project, name="Intake", created_by=create_user)


def file_intake(workspace, project, intake, name, status_value, tagged_as=None, dimension=None, state=None):
    issue = Issue.objects.create(workspace=workspace, project=project, name=name, state=state)
    if tagged_as is not None:
        WorkItemPropertyValue.objects.create(
            workspace=workspace, project=project, property=dimension, issue=issue, value=tagged_as
        )
    return IntakeIssue.objects.create(
        workspace=workspace, project=project, intake=intake, issue=issue, status=status_value
    )


def frontline_url(workspace, project):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/frontline/"


def attention_url(workspace, project):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/attention/"


@pytest.mark.contract
@pytest.mark.django_db
class TestFrontline:
    def test_the_panel_stays_off_until_a_project_marks_a_dimension(
        self, session_client, workspace, project, intake
    ):
        """No configuration means no panel, not an empty frame."""
        file_intake(workspace, project, intake, "Export times out", -2)

        body = session_client.get(frontline_url(workspace, project)).json()

        assert body["dimension"] is None
        assert body["groups"] == []

    def test_intake_groups_under_the_project_s_own_headings(
        self, session_client, workspace, project, intake, dimension
    ):
        file_intake(workspace, project, intake, "Export times out", -2, ["acme"], dimension)
        file_intake(workspace, project, intake, "Login flakes", 1, ["acme"], dimension)
        file_intake(workspace, project, intake, "Slow search", -2, ["globex"], dimension)

        body = session_client.get(frontline_url(workspace, project)).json()

        assert body["dimension"]["name"] == "合作單位"
        assert [(group["label"], group["total"]) for group in body["groups"]] == [("Acme 工業", 2), ("Globex", 1)]

    def test_a_report_from_two_customers_appears_under_both(
        self, session_client, workspace, project, intake, dimension
    ):
        file_intake(workspace, project, intake, "Shared bug", -2, ["acme", "globex"], dimension)

        groups = session_client.get(frontline_url(workspace, project)).json()["groups"]

        assert {group["value"] for group in groups} == {"acme", "globex"}
        assert all(group["items"][0]["name"] == "Shared bug" for group in groups)

    def test_untagged_intake_is_shown_last_rather_than_hidden(
        self, session_client, workspace, project, intake, dimension
    ):
        """The untagged pile is how much nobody has attributed. Hiding it flatters."""
        file_intake(workspace, project, intake, "Tagged", -2, ["acme"], dimension)
        file_intake(workspace, project, intake, "Nobody claimed this", -2)

        groups = session_client.get(frontline_url(workspace, project)).json()["groups"]

        assert groups[-1]["value"] is None
        assert groups[-1]["items"][0]["name"] == "Nobody claimed this"

    def test_statuses_fold_into_the_three_answers_a_reader_wants(
        self, session_client, workspace, project, intake, dimension
    ):
        file_intake(workspace, project, intake, "Waiting", -2, ["acme"], dimension)
        file_intake(workspace, project, intake, "Snoozed", 0, ["acme"], dimension)
        file_intake(workspace, project, intake, "Scheduled", 1, ["acme"], dimension)
        file_intake(workspace, project, intake, "Turned down", -1, ["acme"], dimension)
        file_intake(workspace, project, intake, "Already known", 2, ["acme"], dimension)

        body = session_client.get(frontline_url(workspace, project)).json()

        assert body["totals"] == {"pending": 2, "accepted": 1, "declined": 2}

    def test_a_group_is_capped_but_says_how_many_it_holds(
        self, session_client, workspace, project, intake, dimension
    ):
        for index in range(8):
            file_intake(workspace, project, intake, f"Report {index}", -2, ["acme"], dimension)

        group = session_client.get(frontline_url(workspace, project)).json()["groups"][0]

        assert group["total"] == 8
        assert len(group["items"]) == 5

    def test_a_renamed_option_still_renders_its_rows(
        self, session_client, workspace, project, intake, dimension
    ):
        """Losing the option must not lose the work item filed against it."""
        file_intake(workspace, project, intake, "Old account", -2, ["retired-value"], dimension)

        groups = session_client.get(frontline_url(workspace, project)).json()["groups"]

        assert groups[0]["label"] == "retired-value"


@pytest.mark.contract
@pytest.mark.django_db
class TestAttention:
    def _issue(self, workspace, project, name, state, **extra):
        return Issue.objects.create(workspace=workspace, project=project, name=name, state=state, **extra)

    def test_overdue_comes_before_urgent(self, session_client, workspace, project, states):
        """A missed date is a fact; a priority is an opinion."""
        today = timezone.now().date()
        self._issue(workspace, project, "Urgent but not late", states["started"], priority="urgent")
        self._issue(
            workspace, project, "Late", states["started"], target_date=today - timezone.timedelta(days=3)
        )

        items = session_client.get(attention_url(workspace, project)).json()["items"]

        assert [item["name"] for item in items] == ["Late", "Urgent but not late"]
        assert items[0]["days_overdue"] == 3

    def test_finished_work_is_not_something_to_do_today(self, session_client, workspace, project, states):
        today = timezone.now().date()
        self._issue(
            workspace, project, "Shipped late", states["completed"], target_date=today - timezone.timedelta(days=9)
        )

        body = session_client.get(attention_url(workspace, project)).json()

        assert body["items"] == []
        assert body["total_overdue"] == 0

    def test_one_item_that_is_both_appears_once(self, session_client, workspace, project, states):
        today = timezone.now().date()
        self._issue(
            workspace,
            project,
            "Late and urgent",
            states["started"],
            priority="urgent",
            target_date=today - timezone.timedelta(days=1),
        )

        items = session_client.get(attention_url(workspace, project)).json()["items"]

        assert [item["name"] for item in items] == ["Late and urgent"]

    def test_the_cap_reports_what_it_held_back(self, session_client, workspace, project, states):
        today = timezone.now().date()
        for index in range(7):
            self._issue(
                workspace,
                project,
                f"Late {index}",
                states["started"],
                target_date=today - timezone.timedelta(days=index + 1),
            )

        body = session_client.get(attention_url(workspace, project)).json()

        assert len(body["items"]) == 5
        assert body["total_overdue"] == 7

    def test_the_oldest_miss_leads(self, session_client, workspace, project, states):
        today = timezone.now().date()
        self._issue(workspace, project, "Two days", states["started"], target_date=today - timezone.timedelta(days=2))
        self._issue(workspace, project, "Ten days", states["started"], target_date=today - timezone.timedelta(days=10))

        items = session_client.get(attention_url(workspace, project)).json()["items"]

        assert [item["name"] for item in items] == ["Ten days", "Two days"]

    def test_misses_of_the_same_age_are_broken_by_priority(self, session_client, workspace, project, states):
        """`priority` is a CharField, so ordering by the column would put urgent below none."""
        same_day = timezone.now().date() - timezone.timedelta(days=2)
        self._issue(workspace, project, "Low", states["started"], priority="low", target_date=same_day)
        self._issue(workspace, project, "Urgent", states["started"], priority="urgent", target_date=same_day)
        self._issue(workspace, project, "Medium", states["started"], priority="medium", target_date=same_day)

        items = session_client.get(attention_url(workspace, project)).json()["items"]

        assert [item["name"] for item in items] == ["Urgent", "Medium", "Low"]

    def test_an_urgent_item_with_a_date_leads_one_without(self, session_client, workspace, project, states):
        """A date is a commitment; no date is only an opinion about ordering."""
        soon = timezone.now().date() + timezone.timedelta(days=2)
        self._issue(workspace, project, "No date", states["started"], priority="urgent")
        self._issue(workspace, project, "Due soon", states["started"], priority="urgent", target_date=soon)

        items = session_client.get(attention_url(workspace, project)).json()["items"]

        assert [item["name"] for item in items] == ["Due soon", "No date"]

    def test_who_is_on_it_comes_with_the_row(self, session_client, workspace, project, states, create_user):
        today = timezone.now().date()
        issue = self._issue(
            workspace, project, "Late", states["started"], target_date=today - timezone.timedelta(days=1)
        )
        IssueAssignee.objects.create(workspace=workspace, project=project, issue=issue, assignee=create_user)

        items = session_client.get(attention_url(workspace, project)).json()["items"]

        assert [assignee["id"] for assignee in items[0]["assignees"]] == [str(create_user.id)]
