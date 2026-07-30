# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""One property applied to a selection.

The neighbouring bulk-date endpoint takes a per-item payload because each item gets its own
dates. This is the other shape -- one value across a multi-select -- and the two differences
that matter are which properties it will accept at all, and that labels and assignees add
rather than replace.
"""

import pytest
from rest_framework import status

from plane.db.models import Issue, IssueLabel, Label, Project, ProjectMember, State


@pytest.fixture
def bulk_project(db, workspace, create_user):
    project = Project.objects.create(name="Bulk", identifier="BULK", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20, is_active=True)
    return project


def bulk_url(workspace, project):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/bulk-update-issues/"


@pytest.mark.contract
@pytest.mark.django_db
class TestBulkUpdate:
    def _items(self, workspace, project, count=3):
        return [
            Issue.objects.create(workspace=workspace, project=project, name=f"Item {index}")
            for index in range(count)
        ]

    def test_one_state_is_applied_to_the_whole_selection(self, session_client, workspace, bulk_project):
        items = self._items(workspace, bulk_project)
        done = State.objects.create(
            workspace=workspace, project=bulk_project, name="Done", group="completed", sequence=1000
        )

        response = session_client.post(
            bulk_url(workspace, bulk_project),
            data={"issue_ids": [str(i.id) for i in items], "properties": {"state_id": str(done.id)}},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["updated"] == 3
        for item in items:
            item.refresh_from_db()
            assert item.state_id == done.id

    def test_labels_are_added_rather_than_replaced(self, session_client, workspace, bulk_project, create_user):
        items = self._items(workspace, bulk_project, count=2)
        existing = Label.objects.create(workspace=workspace, project=bulk_project, name="keep")
        incoming = Label.objects.create(workspace=workspace, project=bulk_project, name="add")
        IssueLabel.objects.create(
            issue=items[0], label=existing, project=bulk_project, workspace=workspace, created_by=create_user
        )

        response = session_client.post(
            bulk_url(workspace, bulk_project),
            data={"issue_ids": [str(i.id) for i in items], "properties": {"label_ids": [str(incoming.id)]}},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        # "Add a label to these" is the operation people mean. Replacing would strip `keep`.
        assert set(IssueLabel.objects.filter(issue=items[0]).values_list("label__name", flat=True)) == {"keep", "add"}
        assert set(IssueLabel.objects.filter(issue=items[1]).values_list("label__name", flat=True)) == {"add"}

    def test_applying_the_same_label_twice_is_not_an_error(self, session_client, workspace, bulk_project):
        items = self._items(workspace, bulk_project, count=1)
        label = Label.objects.create(workspace=workspace, project=bulk_project, name="dup")
        payload = {"issue_ids": [str(items[0].id)], "properties": {"label_ids": [str(label.id)]}}

        session_client.post(bulk_url(workspace, bulk_project), data=payload, content_type="application/json")
        second = session_client.post(bulk_url(workspace, bulk_project), data=payload, content_type="application/json")

        assert second.status_code == status.HTTP_200_OK
        assert IssueLabel.objects.filter(issue=items[0], label=label).count() == 1

    def test_per_item_properties_are_refused_rather_than_silently_ignored(
        self, session_client, workspace, bulk_project
    ):
        """A bulk endpoint that accepted `name` would be a way to retitle fifty items alike."""
        items = self._items(workspace, bulk_project, count=1)

        response = session_client.post(
            bulk_url(workspace, bulk_project),
            data={"issue_ids": [str(items[0].id)], "properties": {"name": "Same name for all"}},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        items[0].refresh_from_db()
        assert items[0].name == "Item 0"

    def test_an_empty_selection_is_refused(self, session_client, workspace, bulk_project):
        response = session_client.post(
            bulk_url(workspace, bulk_project),
            data={"issue_ids": [], "properties": {"priority": "high"}},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_work_items_from_another_project_are_not_reachable(
        self, session_client, workspace, bulk_project, create_user
    ):
        other = Project.objects.create(name="Other", identifier="OTH2", workspace=workspace, created_by=create_user)
        ProjectMember.objects.create(workspace=workspace, project=other, member=create_user, role=20, is_active=True)
        elsewhere = Issue.objects.create(workspace=workspace, project=other, name="Not yours")

        response = session_client.post(
            bulk_url(workspace, bulk_project),
            data={"issue_ids": [str(elsewhere.id)], "properties": {"priority": "urgent"}},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        elsewhere.refresh_from_db()
        assert elsewhere.priority == "none"
