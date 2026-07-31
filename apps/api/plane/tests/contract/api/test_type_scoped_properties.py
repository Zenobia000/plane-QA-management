# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""What narrowing a property to a work item type is allowed to change.

The interesting cases are all about the boundary: an untyped property still reaches
everything, a narrowed one reaches only its own type, and neither can be required of an
item that is never shown it. The two ways to write a value -- through the work-item
serializer and through the value endpoint -- are both checked, because the second bypasses
the first entirely.
"""

import pytest
from rest_framework import status

from plane.db.models import (
    Issue,
    IssueType,
    Project,
    ProjectIssueType,
    ProjectMember,
    WorkItemProperty,
    WorkItemPropertyValue,
)


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(
        name="Type scoped properties",
        identifier="TSP",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20, is_active=True)
    return project


def _enabled_type(workspace, project, name, **kwargs):
    """A type the project has actually switched on.

    The work-item serializer refuses a type that is not enabled here, so a fixture that
    only creates the IssueType produces a 400 that looks like a property failure and is not.
    """
    issue_type = IssueType.objects.create(workspace=workspace, name=name, **kwargs)
    ProjectIssueType.objects.create(workspace=workspace, project=project, issue_type=issue_type)
    return issue_type


@pytest.fixture
def bug_type(db, workspace, project):
    return _enabled_type(workspace, project, "Bug", level=2)


@pytest.fixture
def epic_type(db, workspace, project):
    return _enabled_type(workspace, project, "Epic", level=0, is_epic=True)


def _property(project, workspace, name, *, type=None, is_required=False):
    return WorkItemProperty.objects.create(
        project=project,
        workspace=workspace,
        name=name,
        kind=WorkItemProperty.Kind.TEXT,
        type=type,
        is_required=is_required,
    )


@pytest.mark.contract
@pytest.mark.django_db
class TestTypeScopedProperties:
    def test_untyped_property_still_applies_to_every_type(
        self, session_client, workspace, project, bug_type
    ):
        """Every property that existed before narrowing was possible is untyped.

        If this stops being true, the migration silently changed what every existing project
        asks for.
        """
        prop = _property(project, workspace, "Notes")
        issue = Issue.objects.create(workspace=workspace, project=project, name="Any item", type=bug_type)

        response = session_client.put(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}"
            f"/properties/{prop.id}/",
            {"value": "anything"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK

    def test_narrowed_property_is_refused_on_another_type(
        self, session_client, workspace, project, bug_type, epic_type
    ):
        """The value endpoint writes directly, so it is the way around the serializer."""
        severity = _property(project, workspace, "Severity", type=bug_type)
        epic = Issue.objects.create(workspace=workspace, project=project, name="An epic", type=epic_type)

        response = session_client.put(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{epic.id}"
            f"/properties/{severity.id}/",
            {"value": "high"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not WorkItemPropertyValue.objects.filter(issue=epic, property=severity).exists()

    def test_narrowed_property_is_accepted_on_its_own_type(
        self, session_client, workspace, project, bug_type
    ):
        severity = _property(project, workspace, "Severity", type=bug_type)
        bug = Issue.objects.create(workspace=workspace, project=project, name="A bug", type=bug_type)

        response = session_client.put(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/work-items/{bug.id}"
            f"/properties/{severity.id}/",
            {"value": "high"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK

    def test_required_narrowed_property_does_not_block_other_types(
        self, api_key_client, workspace, project, bug_type, epic_type
    ):
        """The failure this guards: a required Bug field making every Epic uncreatable.

        Before narrowing existed, every required property was required of everything, so
        this is the case that makes the feature worth having.
        """
        _property(project, workspace, "Steps to reproduce", type=bug_type, is_required=True)

        response = api_key_client.post(
            f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/work-items/",
            {"name": "An epic with no repro steps", "type": str(epic_type.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_required_narrowed_property_still_binds_its_own_type(
        self, api_key_client, workspace, project, bug_type
    ):
        _property(project, workspace, "Steps to reproduce", type=bug_type, is_required=True)

        response = api_key_client.post(
            f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/work-items/",
            {"name": "A bug with no repro steps", "type": str(bug_type.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Steps to reproduce" in str(response.json())

    def test_two_types_may_each_carry_a_property_of_the_same_name(
        self, db, workspace, project, bug_type, epic_type
    ):
        """A Bug's Severity and an Epic's Severity are different fields that share a word."""
        _property(project, workspace, "Severity", type=bug_type)
        _property(project, workspace, "Severity", type=epic_type)

        assert WorkItemProperty.objects.filter(project=project, name="Severity").count() == 2

    def test_untyped_names_are_still_unique_within_a_project(self, db, workspace, project):
        """Postgres treats NULLs as distinct, so this needs its own constraint to hold."""
        from django.db import IntegrityError, transaction

        _property(project, workspace, "Notes")
        with pytest.raises(IntegrityError), transaction.atomic():
            _property(project, workspace, "Notes")

    def test_serializer_refuses_a_property_belonging_to_another_type(
        self, api_key_client, workspace, project, bug_type, epic_type
    ):
        """The other write path. Creating with the value inline must be refused too."""
        severity = _property(project, workspace, "Severity", type=bug_type)

        response = api_key_client.post(
            f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/work-items/",
            {
                "name": "An epic claiming a bug field",
                "type": str(epic_type.id),
                "properties": {str(severity.id): "high"},
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not Issue.objects.filter(project=project, name="An epic claiming a bug field").exists()

    def test_retyping_resolves_against_the_incoming_type(
        self, api_key_client, workspace, project, bug_type, epic_type
    ):
        """The incoming type decides which properties apply, not the stored one.

        Retyping an Epic to Bug in the same request that sets a Bug-only property has to be
        accepted; resolving against the stored type would reject a payload that is coherent.
        """
        severity = _property(project, workspace, "Severity", type=bug_type)
        epic = Issue.objects.create(workspace=workspace, project=project, name="Becoming a bug", type=epic_type)

        response = api_key_client.patch(
            f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/work-items/{epic.id}/",
            {"type": str(bug_type.id), "properties": {str(severity.id): "high"}},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
