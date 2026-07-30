# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""What the Project Overview reads and writes.

The interesting cases are the ones ADR 0005 accepted a cost for. `EntityUpdate` keys its
target by a bare UUID, so the database cannot stop an update pointing across a project
boundary and cannot remove updates when their entity goes away -- both are the
application's job, and both are pinned here. The rest is ordinary project-scoped CRUD.
"""

import pytest
from rest_framework import status

from plane.bgtasks.deletion_task import soft_delete_related_objects
from plane.db.models import EntityUpdate, Issue, Milestone, Project, ProjectMember, State


@pytest.fixture
def overview_project(db, workspace, create_user):
    project = Project.objects.create(
        name="Overview", identifier="OVRV", workspace=workspace, created_by=create_user
    )
    ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20, is_active=True)
    return project


@pytest.fixture
def other_project(db, workspace, create_user):
    project = Project.objects.create(name="Other", identifier="OTHR", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20, is_active=True)
    return project


def project_url(workspace, project):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/"


def overview_url(workspace, project):
    return f"{project_url(workspace, project)}overview/"


def progress_url(workspace, project):
    return f"{project_url(workspace, project)}progress/"


def links_url(workspace, project):
    return f"{project_url(workspace, project)}links/"


def updates_url(workspace, project):
    return f"{project_url(workspace, project)}updates/"


@pytest.mark.contract
@pytest.mark.django_db
class TestProjectAttributes:
    def test_the_overview_properties_round_trip(self, session_client, workspace, overview_project):
        response = session_client.patch(
            project_url(workspace, overview_project),
            data={
                "state": "in_progress",
                "priority": "high",
                "start_date": "2026-08-01",
                "target_date": "2026-12-31",
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        overview_project.refresh_from_db()
        assert overview_project.state == "in_progress"
        assert overview_project.priority == "high"
        assert str(overview_project.start_date) == "2026-08-01"
        assert str(overview_project.target_date) == "2026-12-31"

    def test_a_project_created_without_them_is_valid(self, session_client, workspace, overview_project):
        """Additive and optional: nothing that worked before has to start sending these."""
        assert overview_project.state is None
        assert overview_project.priority == "none"
        assert overview_project.start_date is None

    def test_the_state_vocabulary_is_the_portfolio_one(self, session_client, workspace, overview_project):
        response = session_client.patch(
            project_url(workspace, overview_project),
            data={"state": "shipping"},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.contract
@pytest.mark.django_db
class TestProjectProgress:
    def _state(self, workspace, project, name, group):
        return State.objects.create(workspace=workspace, project=project, name=name, group=group, sequence=1000)

    def test_completion_is_computed_over_work_that_is_still_owed(
        self, session_client, workspace, overview_project
    ):
        """Cancelled work leaves the denominator.

        Two of five items done and one cancelled is 2/4, not 2/5. Counting cancelled work as
        outstanding reports a project as behind on work nobody owes.
        """
        done = self._state(workspace, overview_project, "Done", "completed")
        started = self._state(workspace, overview_project, "Doing", "started")
        dropped = self._state(workspace, overview_project, "Dropped", "cancelled")
        for name, state in (
            ("A", done),
            ("B", done),
            ("C", started),
            ("D", started),
            ("E", dropped),
        ):
            Issue.objects.create(workspace=workspace, project=overview_project, name=name, state=state)

        response = session_client.get(progress_url(workspace, overview_project))

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["total"] == 5
        assert body["in_scope"] == 4
        assert body["completed"] == 2
        assert body["completion_percentage"] == 50

    def test_an_empty_project_reports_zero_rather_than_dividing_by_it(
        self, session_client, workspace, overview_project
    ):
        response = session_client.get(progress_url(workspace, overview_project))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["completion_percentage"] == 0


@pytest.mark.contract
@pytest.mark.django_db
class TestProjectLinks:
    def test_a_link_is_created_and_listed_against_its_project(
        self, session_client, workspace, overview_project
    ):
        created = session_client.post(
            links_url(workspace, overview_project),
            data={"title": "Runbook", "url": "runbooks.example.com/overview"},
            content_type="application/json",
        )

        assert created.status_code == status.HTTP_201_CREATED
        # Pasting a bare host is the common case and works the same way it does on modules.
        assert created.json()["url"].startswith("http://")

        listed = session_client.get(links_url(workspace, overview_project))
        assert [row["title"] for row in listed.json()] == ["Runbook"]

    def test_links_do_not_leak_between_projects(
        self, session_client, workspace, overview_project, other_project
    ):
        session_client.post(
            links_url(workspace, overview_project),
            data={"url": "https://example.com/one"},
            content_type="application/json",
        )

        listed = session_client.get(links_url(workspace, other_project))
        assert listed.json() == []


@pytest.mark.contract
@pytest.mark.django_db
class TestEntityUpdates:
    def test_a_project_update_defaults_to_this_project(self, session_client, workspace, overview_project):
        created = session_client.post(
            updates_url(workspace, overview_project),
            data={
                "entity_name": "project",
                "entity_identifier": str(overview_project.id),
                "status": "at_risk",
                "description": "Vendor slipped a week.",
            },
            content_type="application/json",
        )

        assert created.status_code == status.HTTP_201_CREATED

        # The list needs no identifier: the overview is already addressing the project.
        listed = session_client.get(updates_url(workspace, overview_project))
        assert [row["status"] for row in listed.json()] == ["at_risk"]

    def test_the_same_model_carries_work_item_updates(self, session_client, workspace, overview_project):
        """The whole point of one table: no schema change to reach the second entity."""
        work_item = Issue.objects.create(workspace=workspace, project=overview_project, name="Ship it")

        created = session_client.post(
            updates_url(workspace, overview_project),
            data={
                "entity_name": "work_item",
                "entity_identifier": str(work_item.id),
                "status": "on_track",
                "description": "Review done.",
            },
            content_type="application/json",
        )

        assert created.status_code == status.HTTP_201_CREATED

        listed = session_client.get(
            updates_url(workspace, overview_project),
            {"entity_name": "work_item", "entity_identifier": str(work_item.id)},
        )
        assert [row["description"] for row in listed.json()] == ["Review done."]

        # And it does not show up on the project's own thread.
        assert session_client.get(updates_url(workspace, overview_project)).json() == []

    def test_replies_hang_off_their_update_rather_than_beside_it(
        self, session_client, workspace, overview_project
    ):
        """Without the parent split a thread reads as a run of unrelated status posts."""
        root = session_client.post(
            updates_url(workspace, overview_project),
            data={
                "entity_name": "project",
                "entity_identifier": str(overview_project.id),
                "status": "at_risk",
                "description": "Vendor slipped.",
            },
            content_type="application/json",
        ).json()

        reply = session_client.post(
            updates_url(workspace, overview_project),
            data={
                "entity_name": "project",
                "entity_identifier": str(overview_project.id),
                "status": "at_risk",
                "description": "Escalated to their account team.",
                "parent": root["id"],
            },
            content_type="application/json",
        )
        assert reply.status_code == status.HTTP_201_CREATED

        top_level = session_client.get(updates_url(workspace, overview_project)).json()
        assert [row["description"] for row in top_level] == ["Vendor slipped."]
        assert top_level[0]["reply_count"] == 1

        replies = session_client.get(updates_url(workspace, overview_project), {"parent": root["id"]}).json()
        assert [row["description"] for row in replies] == ["Escalated to their account team."]

    def test_a_reply_cannot_cross_a_project_boundary(
        self, session_client, workspace, overview_project, other_project
    ):
        elsewhere = session_client.post(
            updates_url(workspace, other_project),
            data={
                "entity_name": "project",
                "entity_identifier": str(other_project.id),
                "status": "on_track",
            },
            content_type="application/json",
        ).json()

        response = session_client.post(
            updates_url(workspace, overview_project),
            data={
                "entity_name": "project",
                "entity_identifier": str(overview_project.id),
                "status": "on_track",
                "parent": elsewhere["id"],
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_an_update_cannot_name_another_projects_work_item(
        self, session_client, workspace, overview_project, other_project
    ):
        """The cost of a bare UUID target, paid in the serializer because the DB cannot."""
        elsewhere = Issue.objects.create(workspace=workspace, project=other_project, name="Not yours")

        response = session_client.post(
            updates_url(workspace, overview_project),
            data={
                "entity_name": "work_item",
                "entity_identifier": str(elsewhere.id),
                "status": "on_track",
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not EntityUpdate.objects.filter(entity_identifier=elsewhere.id).exists()

    def test_a_project_update_cannot_name_a_different_project(
        self, session_client, workspace, overview_project, other_project
    ):
        response = session_client.post(
            updates_url(workspace, overview_project),
            data={
                "entity_name": "project",
                "entity_identifier": str(other_project.id),
                "status": "on_track",
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_the_deletion_task_takes_a_work_items_updates_with_it(
        self, session_client, workspace, overview_project
    ):
        """No foreign key means no database cascade, so the delete path has to do it.

        The task is invoked directly. `SoftDeleteModel.delete()` reaches it through
        `.delay()`, and Celery is not eager in this suite, so calling `delete()` here would
        assert on the queue rather than on the behaviour -- which is equally true of the
        relation cascade this sweep sits beside. Removal is therefore asynchronous, on the
        same terms as every other cascade in the codebase.
        """
        work_item = Issue.objects.create(workspace=workspace, project=overview_project, name="Doomed")
        session_client.post(
            updates_url(workspace, overview_project),
            data={
                "entity_name": "work_item",
                "entity_identifier": str(work_item.id),
                "status": "off_track",
            },
            content_type="application/json",
        )
        survivor = Issue.objects.create(workspace=workspace, project=overview_project, name="Fine")
        session_client.post(
            updates_url(workspace, overview_project),
            data={
                "entity_name": "work_item",
                "entity_identifier": str(survivor.id),
                "status": "on_track",
            },
            content_type="application/json",
        )

        soft_delete_related_objects("db", "issue", work_item.pk)

        assert EntityUpdate.objects.filter(entity_identifier=work_item.id).count() == 0
        # Scoped to the entity going away, not to the project it was in.
        assert EntityUpdate.objects.filter(entity_identifier=survivor.id).count() == 1


@pytest.mark.contract
@pytest.mark.django_db
class TestOverviewComposite:
    def test_one_request_returns_progress_links_and_updates(
        self, session_client, workspace, overview_project
    ):
        session_client.post(
            links_url(workspace, overview_project),
            data={"url": "https://example.com/spec"},
            content_type="application/json",
        )
        session_client.post(
            updates_url(workspace, overview_project),
            data={
                "entity_name": "project",
                "entity_identifier": str(overview_project.id),
                "status": "on_track",
            },
            content_type="application/json",
        )

        response = session_client.get(overview_url(workspace, overview_project))

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert set(body) == {"progress", "links", "updates", "milestones"}
        assert len(body["links"]) == 1
        assert len(body["updates"]) == 1
        assert body["progress"]["completion_percentage"] == 0

    def test_milestones_arrive_with_the_counts_that_make_them_worth_showing(
        self, session_client, workspace, overview_project
    ):
        done = State.objects.create(
            workspace=workspace, project=overview_project, name="Done", group="completed", sequence=1000
        )
        # Both states are named explicitly: `Issue.save()` back-fills a missing state from
        # the project, so leaving one blank in a project whose only state is "Done" would
        # have silently made every item complete.
        todo = State.objects.create(
            workspace=workspace, project=overview_project, name="Todo", group="unstarted", sequence=2000
        )
        milestone = Milestone.objects.create(
            workspace=workspace, project=overview_project, name="Beta", target_date="2026-09-30"
        )
        Issue.objects.create(
            workspace=workspace, project=overview_project, name="A", state=done, milestone=milestone
        )
        Issue.objects.create(
            workspace=workspace, project=overview_project, name="B", state=todo, milestone=milestone
        )

        body = session_client.get(overview_url(workspace, overview_project)).json()

        # A milestone without counts is decoration; the reason to show one is to see what
        # is left.
        assert body["milestones"] == [
            {
                "id": str(milestone.id),
                "name": "Beta",
                "status": "planned",
                "target_date": "2026-09-30",
                "total": 2,
                "completed": 1,
            }
        ]

    def test_a_non_member_cannot_read_the_overview(self, api_client, workspace, overview_project):
        response = api_client.get(overview_url(workspace, overview_project))

        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
