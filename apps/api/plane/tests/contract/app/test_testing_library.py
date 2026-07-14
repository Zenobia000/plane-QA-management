# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from rest_framework import status

from plane.db.models import Issue, Project, ProjectMember, TestCase
from plane.testing import create_test_case, create_test_folder, link_test_case_to_work_item


@pytest.fixture
def testing_project(db, workspace, create_user):
    project = Project.objects.create(
        name="Testing API",
        identifier="TAPI",
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


def _cases_url(workspace, project):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/testing/test-cases/"


def _case_url(workspace, project, test_case_id):
    return f"{_cases_url(workspace, project)}{test_case_id}/"


@pytest.mark.contract
@pytest.mark.django_db
class TestTestingLibraryAPI:
    def test_create_and_retrieve_test_case(self, session_client, workspace, testing_project):
        response = session_client.post(
            _cases_url(workspace, testing_project),
            {
                "title": "Checkout succeeds",
                "priority": "high",
                "steps": [
                    {
                        "action": {"type": "text", "value": "Submit cart"},
                        "expected_result": {"type": "text", "value": "Order is confirmed"},
                    }
                ],
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        payload = response.json()
        assert payload["sequence"] == 1
        assert payload["current"]["title"] == "Checkout succeeds"
        assert payload["current"]["steps"][0]["position"] == 1

        retrieved = session_client.get(_case_url(workspace, testing_project, payload["id"]))
        assert retrieved.status_code == status.HTTP_200_OK
        assert retrieved.json()["current"]["priority"] == "high"

    def test_patch_creates_new_version(self, session_client, workspace, testing_project):
        created = session_client.post(
            _cases_url(workspace, testing_project), {"title": "Original"}, format="json"
        ).json()

        updated = session_client.patch(
            _case_url(workspace, testing_project, created["id"]),
            {"title": "Revised"},
            format="json",
        )

        assert updated.status_code == status.HTTP_200_OK
        assert updated.json()["current_version"] == 2
        assert updated.json()["current"]["title"] == "Revised"
        original_url = f"{_case_url(workspace, testing_project, created['id'])}versions/1/"
        original = session_client.get(original_url)
        assert original.status_code == status.HTTP_200_OK
        assert original.json()["title"] == "Original"

    def test_search_uses_current_title(self, session_client, workspace, testing_project):
        created = session_client.post(
            _cases_url(workspace, testing_project), {"title": "Old checkout title"}, format="json"
        ).json()
        session_client.patch(
            _case_url(workspace, testing_project, created["id"]),
            {"title": "New payment title"},
            format="json",
        )

        old_results = session_client.get(_cases_url(workspace, testing_project), {"search": "checkout"})
        new_results = session_client.get(_cases_url(workspace, testing_project), {"search": "payment"})

        assert old_results.json() == []
        assert len(new_results.json()) == 1

    def test_library_cursor_pagination_is_stable(self, session_client, workspace, testing_project):
        for title in ("First", "Second", "Third"):
            session_client.post(_cases_url(workspace, testing_project), {"title": title}, format="json")
        first_page = session_client.get(_cases_url(workspace, testing_project), {"per_page": 2}).json()
        second_page = session_client.get(
            _cases_url(workspace, testing_project),
            {"per_page": 2, "cursor": first_page["next_cursor"]},
        ).json()
        assert [item["sequence"] for item in first_page["results"]] == [1, 2]
        assert [item["sequence"] for item in second_page["results"]] == [3]
        assert first_page["total_count"] == 3

    def test_archive_removes_case_from_active_list(self, session_client, workspace, testing_project):
        created = session_client.post(
            _cases_url(workspace, testing_project), {"title": "Archive me"}, format="json"
        ).json()

        archived = session_client.delete(_case_url(workspace, testing_project, created["id"]))

        assert archived.status_code == status.HTTP_204_NO_CONTENT
        assert session_client.get(_cases_url(workspace, testing_project)).json() == []
        assert TestCase.objects.filter(id=created["id"], archived_at__isnull=False).exists()

    def test_link_requirement_stays_inside_project(self, session_client, workspace, testing_project):
        created = session_client.post(
            _cases_url(workspace, testing_project), {"title": "Covers checkout"}, format="json"
        ).json()
        requirement = Issue.objects.create(
            workspace=workspace,
            project=testing_project,
            name="Checkout requirement",
            sequence_id=1,
        )
        link_url = f"{_case_url(workspace, testing_project, created['id'])}work-items/"

        linked = session_client.post(link_url, {"issue_id": str(requirement.id)}, format="json")

        assert linked.status_code == status.HTTP_201_CREATED
        detail = session_client.get(_case_url(workspace, testing_project, created["id"])).json()
        assert detail["work_item_ids"] == [str(requirement.id)]
        filtered = session_client.get(
            _cases_url(workspace, testing_project), {"work_item_id": str(requirement.id)}
        )
        assert [item["id"] for item in filtered.json()] == [created["id"]]

        other_project = Project.objects.create(
            name="Other Project",
            identifier="OTHER",
            workspace=workspace,
        )
        foreign_requirement = Issue.objects.create(
            workspace=workspace,
            project=other_project,
            name="Foreign requirement",
            sequence_id=1,
        )
        rejected = session_client.post(link_url, {"issue_id": str(foreign_requirement.id)}, format="json")
        assert rejected.status_code == status.HTTP_404_NOT_FOUND

    def test_csv_round_trip_preserves_folder_steps_and_requirement_links(
        self, session_client, workspace, testing_project
    ):
        parent = create_test_folder(project_id=testing_project.id, name="Checkout")
        child = create_test_folder(project_id=testing_project.id, name="Cards", parent_id=parent.id)
        test_case = create_test_case(
            project_id=testing_project.id,
            title="Visa succeeds",
            folder_id=child.id,
            preconditions={"text": "A cart exists"},
            tags=["smoke", "payment"],
            steps=[{"action": {"text": "Pay"}, "expected_result": {"text": "Approved"}}],
        )
        requirement = Issue.objects.create(workspace=workspace, project=testing_project, name="Card payment")
        link_test_case_to_work_item(
            test_case_id=test_case.id, issue_id=requirement.id, project_id=testing_project.id
        )
        csv_url = f"/api/workspaces/{workspace.slug}/projects/{testing_project.id}/testing/test-cases.csv"

        exported = session_client.get(csv_url)
        imported = session_client.post(csv_url, {"csv_text": exported.content.decode("utf-8")}, format="json")

        assert exported.status_code == status.HTTP_200_OK
        assert imported.status_code == status.HTTP_201_CREATED
        imported_case = TestCase.objects.get(id=imported.json()["case_ids"][0])
        version = imported_case.versions.get(version=1)
        assert imported_case.folder.name == "Cards"
        assert imported_case.folder.parent.name == "Checkout"
        assert version.tags == ["smoke", "payment"]
        assert version.steps.get(position=1).expected_result == {"text": "Approved"}
        assert imported_case.work_item_links.get().issue_id == requirement.id
