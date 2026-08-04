# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Which work items the coverage report is entitled to call untested.

The report used to count everything. On the authors' own instance that produced eight
"uncovered" rows of which exactly one was a real gap: six were implementation tasks -- how
something gets built, not something the product promises -- and one was a hand-filed bug.
A number that is wrong seven times out of eight is a number people stop reading.

The distinction lives on the type, as a flag someone sets, and deliberately not on the
type's *name*. Types are workspace-owned and users rename and invent them; a query matching
"Story" would report perfect coverage the day a team translated it, and report it in
silence. The default runs the safe way for the same reason -- an unclassified type is
counted, which is noise, rather than dropped, which is a gap that hides itself.
"""

import pytest
from rest_framework import status

from plane.db.models import Issue, IssueType, Project, ProjectIssueType, ProjectMember


@pytest.fixture
def project(db, workspace, create_user):
    made = Project.objects.create(name="Cover", identifier="COV", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(workspace=workspace, project=made, member=create_user, role=20, is_active=True)
    return made


def a_type(workspace, project, name, *, needs_acceptance=True, level=2):
    kind = IssueType.objects.create(
        workspace=workspace, name=name, level=level, needs_acceptance=needs_acceptance
    )
    ProjectIssueType.objects.create(workspace=workspace, project=project, issue_type=kind, level=int(level))
    return kind


def an_item(workspace, project, owner, name, kind=None):
    return Issue.objects.create(workspace=workspace, project=project, name=name, type=kind, created_by=owner)


def coverage(client, workspace, project):
    url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/testing/requirement-coverage/"
    response = client.get(url)
    assert response.status_code == status.HTTP_200_OK
    return response.json()


@pytest.mark.contract
@pytest.mark.django_db
class TestWhatCounts:
    def test_only_types_that_promise_something_are_counted(
        self, session_client, workspace, project, create_user
    ):
        story = a_type(workspace, project, "Story")
        task = a_type(workspace, project, "Task", needs_acceptance=False, level=3)
        an_item(workspace, project, create_user, "Users can export orders", story)
        an_item(workspace, project, create_user, "Build the export worker", task)

        body = coverage(session_client, workspace, project)

        assert [row["name"] for row in body["work_items"]] == ["Users can export orders"]
        assert body["uncovered"] == 1

    def test_a_work_item_with_no_type_is_still_counted(
        self, session_client, workspace, project, create_user
    ):
        """A project that never adopted types must not get an empty report."""
        an_item(workspace, project, create_user, "Untyped requirement")

        body = coverage(session_client, workspace, project)

        assert [row["name"] for row in body["work_items"]] == ["Untyped requirement"]

    def test_an_unclassified_type_is_counted_rather_than_dropped(
        self, session_client, workspace, project, create_user
    ):
        """The default must fail loud. A gap that reports itself as covered is the bad case.

        This is what protects a team that renamed "Story" before the flag existed: their
        type keeps the default and stays in the report.
        """
        invented = a_type(workspace, project, "需求")  # never classified by anyone
        an_item(workspace, project, create_user, "Renamed-type requirement", invented)

        body = coverage(session_client, workspace, project)

        assert [row["name"] for row in body["work_items"]] == ["Renamed-type requirement"]

    def test_a_tasks_contracts_still_roll_up_to_its_story(
        self, session_client, workspace, project, create_user
    ):
        """Excluding a row must not discard the evidence hanging off it.

        Coverage rolls up through the hierarchy, so a contract linked to a task still
        proves something about the story above it -- the task simply stops being asked to
        answer for itself.
        """
        story = a_type(workspace, project, "Story")
        task = a_type(workspace, project, "Task", needs_acceptance=False, level=3)
        parent = an_item(workspace, project, create_user, "Export orders", story)
        child = an_item(workspace, project, create_user, "Write the worker", task)
        child.parent = parent
        child.save()

        body = coverage(session_client, workspace, project)
        rows = {row["name"]: row for row in body["work_items"]}

        assert set(rows) == {"Export orders"}
        # Nothing is linked yet, but the roll-up path is the one under test: the parent's
        # effective set is built from its children whether or not they earn rows.
        assert rows["Export orders"]["covered"] is False


@pytest.mark.contract
@pytest.mark.django_db
def test_the_flag_reaches_the_client(session_client, workspace, project, create_user):
    """Settings needs to render the toggle, so the type payload has to carry it."""
    a_type(workspace, project, "Story")
    a_type(workspace, project, "Task", needs_acceptance=False, level=3)

    response = session_client.get(f"/api/workspaces/{workspace.slug}/work-item-types/")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    rows = payload["results"] if isinstance(payload, dict) else payload
    assert {r["name"]: r["needs_acceptance"] for r in rows} == {"Story": True, "Task": False}


@pytest.mark.contract
@pytest.mark.django_db
class TestSummariesDoNotVoteTwice:
    """An epic is covered exactly when its stories are, so counting it again is one fact
    stated twice. On the authors' instance six epics and features held no contract of their
    own and still added six to the numerator, reporting 94% where the truth was 90%."""

    def test_an_epic_over_covered_stories_is_not_counted_again(
        self, session_client, workspace, project, create_user
    ):
        epic = a_type(workspace, project, "Epic", level=0)
        story = a_type(workspace, project, "Story")
        parent = an_item(workspace, project, create_user, "Checkout", epic)
        for name in ("Pay by card", "Pay by transfer"):
            child = an_item(workspace, project, create_user, name, story)
            child.parent = parent
            child.save()

        body = coverage(session_client, workspace, project)
        rows = {r["name"]: r for r in body["work_items"]}

        # The epic is still listed -- seeing which epic holds the gap is the point of roll-up.
        assert set(rows) == {"Checkout", "Pay by card", "Pay by transfer"}
        assert rows["Checkout"]["counts_toward_coverage"] is False
        assert rows["Pay by card"]["counts_toward_coverage"] is True
        # Two stories, not three rows.
        assert body["total"] == 2
        assert body["uncovered"] == 2

    def test_an_epic_with_nothing_beneath_it_counts_for_itself(
        self, session_client, workspace, project, create_user
    ):
        """It summarises nothing, so it is a promise with no acceptance anywhere -- which is
        a real gap and must not disappear just because of its type."""
        epic = a_type(workspace, project, "Epic", level=0)
        an_item(workspace, project, create_user, "Empty epic", epic)

        body = coverage(session_client, workspace, project)

        assert body["total"] == 1
        assert body["uncovered"] == 1
        assert body["work_items"][0]["counts_toward_coverage"] is True

    def test_a_story_under_an_uncounted_task_still_makes_its_epic_a_summary(
        self, session_client, workspace, project, create_user
    ):
        """The walk is by ancestor, not by direct child -- a task in between is invisible
        to the totals but must not break the chain."""
        epic = a_type(workspace, project, "Epic", level=0)
        task = a_type(workspace, project, "Task", needs_acceptance=False, level=3)
        story = a_type(workspace, project, "Story")
        top = an_item(workspace, project, create_user, "Epic", epic)
        middle = an_item(workspace, project, create_user, "Task", task)
        middle.parent = top
        middle.save()
        leaf = an_item(workspace, project, create_user, "Story", story)
        leaf.parent = middle
        leaf.save()

        body = coverage(session_client, workspace, project)
        rows = {r["name"]: r for r in body["work_items"]}

        assert rows["Epic"]["counts_toward_coverage"] is False
        assert body["total"] == 1
