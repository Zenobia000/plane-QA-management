# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""A quality requirement's pass mark, as four columns instead of a sentence.

`case_type` has been able to say a contract is verified by measuring; nothing could say what
was measured or which number decided it, so "P95 < 2s" lived in the description -- readable by
a person and unreadable by any report.

Nothing here evaluates a result against the threshold. Recording a verdict is still the
caller's statement; this only makes the number a number.

Two rules are worth stating in tests rather than prose. A threshold is metric, operator and
value together or none of them, because two of the three is not a weaker threshold but an
unreadable one. And publishing a new version carries forward what the request did not mention
-- the version is immutable, so a field dropped here is a field silently rewritten.
"""

import pytest
from rest_framework import status

from plane.db.models import Project, ProjectMember


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(
        name="Threshold Project", identifier="THR", workspace=workspace, created_by=create_user
    )
    ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20, is_active=True)
    return project


def cases_url(slug, project_id):
    return f"/api/workspaces/{slug}/projects/{project_id}/testing/test-cases/"


def case_url(slug, project_id, case_id):
    return f"{cases_url(slug, project_id)}{case_id}/"


def create_case(client, slug, project, **overrides):
    payload = {"title": "Checkout stays under 2s at peak", "case_type": "performance", **overrides}
    return client.post(cases_url(slug, project.id), data=payload, content_type="application/json")


@pytest.mark.contract
@pytest.mark.django_db
class TestThresholdsOnCreate:
    def test_a_complete_threshold_is_stored_and_returned(self, session_client, workspace, project):
        response = create_case(
            session_client,
            workspace.slug,
            project,
            threshold_metric="checkout P95 latency",
            threshold_operator="lt",
            threshold_value="2",
            threshold_unit="s",
        )

        assert response.status_code == status.HTTP_201_CREATED
        version = response.json()["current"]
        assert version["threshold_metric"] == "checkout P95 latency"
        assert version["threshold_operator"] == "lt"
        assert float(version["threshold_value"]) == 2.0
        assert version["threshold_unit"] == "s"

    def test_a_case_without_a_threshold_still_works(self, session_client, workspace, project):
        """Most cases are functional and have no pass mark of this shape."""
        response = create_case(session_client, workspace.slug, project, case_type="functional")

        assert response.status_code == status.HTTP_201_CREATED
        version = response.json()["current"]
        assert version["threshold_metric"] == ""
        assert version["threshold_value"] is None

    def test_a_dimensionless_threshold_needs_no_unit(self, session_client, workspace, project):
        """A ratio or a count has no unit, and inventing one would say nothing."""
        response = create_case(
            session_client,
            workspace.slug,
            project,
            threshold_metric="failed logins per hour",
            threshold_operator="lte",
            threshold_value="0",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["current"]["threshold_unit"] == ""

    @pytest.mark.parametrize(
        "partial",
        [
            {"threshold_metric": "checkout P95 latency"},
            {"threshold_operator": "lt"},
            {"threshold_value": "2"},
            {"threshold_metric": "checkout P95 latency", "threshold_operator": "lt"},
            {"threshold_operator": "lt", "threshold_value": "2"},
        ],
        ids=["metric", "operator", "value", "metric+operator", "operator+value"],
    )
    def test_a_half_stated_threshold_is_rejected(self, session_client, workspace, project, partial):
        response = create_case(session_client, workspace.slug, project, **partial)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_a_unit_alone_is_rejected(self, session_client, workspace, project):
        response = create_case(session_client, workspace.slug, project, threshold_unit="s")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_an_operator_outside_the_set_is_rejected(self, session_client, workspace, project):
        response = create_case(
            session_client,
            workspace.slug,
            project,
            threshold_metric="checkout P95 latency",
            threshold_operator="<",
            threshold_value="2",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.contract
@pytest.mark.django_db
class TestThresholdsAcrossVersions:
    def test_changing_a_threshold_publishes_a_new_version(self, session_client, workspace, project):
        """The threshold is part of the contract, so changing it is a new contract."""
        created = create_case(
            session_client,
            workspace.slug,
            project,
            threshold_metric="checkout P95 latency",
            threshold_operator="lt",
            threshold_value="2",
            threshold_unit="s",
        )
        case_id = created.json()["id"]

        patched = session_client.patch(
            case_url(workspace.slug, project.id, case_id),
            data={"threshold_value": "1.5"},
            content_type="application/json",
        )

        assert patched.status_code == status.HTTP_200_OK
        body = patched.json()
        assert body["current_version"] == 2
        assert float(body["current"]["threshold_value"]) == 1.5
        # The old number stays readable -- that is the point of versioning the contract.
        assert body["current"]["threshold_metric"] == "checkout P95 latency"

    def test_editing_the_title_leaves_the_threshold_alone(self, session_client, workspace, project):
        """A field missing from the request must inherit, not reset to the serializer default."""
        created = create_case(
            session_client,
            workspace.slug,
            project,
            threshold_metric="checkout P95 latency",
            threshold_operator="lt",
            threshold_value="2",
            threshold_unit="s",
        )
        case_id = created.json()["id"]

        patched = session_client.patch(
            case_url(workspace.slug, project.id, case_id),
            data={"title": "Checkout stays under 2s at Black Friday peak"},
            content_type="application/json",
        )

        version = patched.json()["current"]
        assert version["threshold_metric"] == "checkout P95 latency"
        assert float(version["threshold_value"]) == 2.0
        assert version["threshold_unit"] == "s"

    def test_editing_the_title_leaves_the_case_type_alone(self, session_client, workspace, project):
        """Pre-existing bug, found by giving the thresholds the same treatment.

        `case_type` was absent from the inherited payload, so renaming a performance case
        published a new version classified `functional` -- quietly, and immutably.
        """
        created = create_case(session_client, workspace.slug, project, case_type="performance")
        case_id = created.json()["id"]

        patched = session_client.patch(
            case_url(workspace.slug, project.id, case_id),
            data={"title": "Renamed"},
            content_type="application/json",
        )

        assert patched.json()["current"]["case_type"] == "performance"

    def test_a_threshold_can_be_cleared_by_naming_all_of_it(self, session_client, workspace, project):
        """Removing a pass mark is a deliberate act, so it takes saying so on every column."""
        created = create_case(
            session_client,
            workspace.slug,
            project,
            threshold_metric="checkout P95 latency",
            threshold_operator="lt",
            threshold_value="2",
            threshold_unit="s",
        )
        case_id = created.json()["id"]

        patched = session_client.patch(
            case_url(workspace.slug, project.id, case_id),
            data={
                "threshold_metric": "",
                "threshold_operator": "",
                "threshold_value": None,
                "threshold_unit": "",
            },
            content_type="application/json",
        )

        assert patched.status_code == status.HTTP_200_OK
        version = patched.json()["current"]
        assert version["threshold_metric"] == ""
        assert version["threshold_value"] is None
