# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from django.core.exceptions import ValidationError

from plane.db.models import Project, ProjectMember, TestCaseVersion
from plane.testing import create_test_case, publish_test_case_version


@pytest.fixture
def testing_project(db, workspace, create_user):
    project = Project.objects.create(
        name="Testing Library",
        identifier="TLIB",
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


@pytest.mark.unit
@pytest.mark.django_db
class TestTestingLibraryModels:
    def test_case_creation_publishes_ordered_version(self, testing_project):
        test_case = create_test_case(
            project_id=testing_project.id,
            title="User can sign in",
            priority="high",
            steps=[
                {"action": {"type": "text", "value": "Open sign in"}},
                {
                    "action": {"type": "text", "value": "Submit credentials"},
                    "expected_result": {"type": "text", "value": "Dashboard opens"},
                },
            ],
        )

        version = test_case.versions.get(version=1)
        assert test_case.sequence == 1
        assert version.title == "User can sign in"
        assert list(version.steps.values_list("position", flat=True)) == [1, 2]

    def test_case_sequences_increment_inside_project(self, testing_project):
        first = create_test_case(project_id=testing_project.id, title="First")
        second = create_test_case(project_id=testing_project.id, title="Second")

        assert (first.sequence, second.sequence) == (1, 2)

    def test_edit_appends_version_and_preserves_original(self, testing_project):
        test_case = create_test_case(project_id=testing_project.id, title="Original")

        publish_test_case_version(
            test_case_id=test_case.id,
            project_id=testing_project.id,
            title="Revised",
        )

        test_case.refresh_from_db()
        assert test_case.current_version == 2
        assert list(test_case.versions.order_by("version").values_list("title", flat=True)) == [
            "Original",
            "Revised",
        ]

    def test_published_version_rejects_mutation(self, testing_project):
        test_case = create_test_case(project_id=testing_project.id, title="Immutable")
        version = test_case.versions.get(version=1)
        version.title = "Mutated"

        with pytest.raises(ValidationError, match="immutable"):
            version.save()

        assert TestCaseVersion.objects.get(id=version.id).title == "Immutable"

