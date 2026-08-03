# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""What collapsing the type vocabulary is allowed to change.

The first run of this command against real data set `quality` on 106 work items and then
erased it again, because the kind-stamping pass ran after the merges and rewrote the whole
target type. `test_merged_quality_survives_the_functional_stamp` is that bug; the rest are
the boundaries it turned out to share -- do not retype what you cannot re-derive, and do
not delete a type someone is still using.
"""

from io import StringIO

import pytest
from django.core.management import call_command

from plane.db.models import Issue, IssueType, Project, ProjectMember


@pytest.fixture
def project(db, workspace, create_user):
    p = Project.objects.create(
        name="Converge", identifier="CVG", workspace=workspace, created_by=create_user
    )
    ProjectMember.objects.create(workspace=workspace, project=p, member=create_user, role=20, is_active=True)
    return p


def _type(workspace, name, level, is_epic=False):
    return IssueType.objects.create(workspace=workspace, name=name, level=level, is_epic=is_epic)


def _issue(workspace, project, name, issue_type):
    return Issue.objects.create(workspace=workspace, project=project, name=name, type=issue_type)


def _run(workspace, apply=False):
    out = StringIO()
    args = ["converge_work_item_types", "--workspace", workspace.slug]
    if apply:
        args.append("--apply")
    call_command(*args, stdout=out)
    return out.getvalue()


@pytest.mark.unit
@pytest.mark.django_db
class TestConvergeWorkItemTypes:
    def test_merged_quality_survives_the_functional_stamp(self, workspace, project):
        """The regression. An NFR merged into Story is still a quality requirement.

        Both passes touch the same rows: the merge classifies them, then the stamp fills in
        whatever the canonical type left blank. Order alone does not protect the first pass
        -- the stamp has to skip rows that already carry a kind.
        """
        story = _type(workspace, "Story", 2)
        nfr = _type(workspace, "NFR", 2)
        quality = _issue(workspace, project, "P95 < 2s", nfr)
        plain = _issue(workspace, project, "Export CSV", story)

        _run(workspace, apply=True)

        quality.refresh_from_db()
        plain.refresh_from_db()
        assert quality.requirement_kind == "quality"
        assert plain.requirement_kind == "functional"

    def test_rename_when_the_target_does_not_exist(self, workspace, project):
        """Renaming touches no rows. A merge into a type created for the purpose would
        rewrite every one of them to say exactly what they already said."""
        work_package = _type(workspace, "Work Package", 3)
        item = _issue(workspace, project, "Build firmware", work_package)

        _run(workspace, apply=True)

        item.refresh_from_db()
        assert item.type_id == work_package.id
        work_package.refresh_from_db()
        assert work_package.name == "Task"

    def test_merge_when_the_target_exists(self, workspace, project):
        epic = _type(workspace, "Epic", 0, is_epic=True)
        work_group = _type(workspace, "Work Group", 0, is_epic=True)
        item = _issue(workspace, project, "Platform", work_group)

        _run(workspace, apply=True)

        item.refresh_from_db()
        assert item.type_id == epic.id
        assert not IssueType.objects.filter(workspace=workspace, name="Work Group").exists()

    def test_unused_non_canonical_type_is_deleted(self, workspace, project):
        _type(workspace, "Quality requirement", 2)

        _run(workspace, apply=True)

        assert not IssueType.objects.filter(workspace=workspace, name="Quality requirement").exists()

    def test_unknown_type_with_rows_is_left_alone(self, workspace, project):
        """Silence would be the dangerous outcome: a type this command does not recognise
        is exactly the case where guessing destroys data."""
        mystery = _type(workspace, "Spike", 2)
        item = _issue(workspace, project, "Investigate", mystery)

        output = _run(workspace, apply=True)

        item.refresh_from_db()
        assert item.type_id == mystery.id
        assert IssueType.objects.filter(workspace=workspace, name="Spike").exists()
        assert "Spike" in output

    def test_dry_run_writes_nothing(self, workspace, project):
        nfr = _type(workspace, "NFR", 2)
        _type(workspace, "Story", 2)
        item = _issue(workspace, project, "P95 < 2s", nfr)

        _run(workspace, apply=False)

        item.refresh_from_db()
        assert item.type_id == nfr.id
        assert item.requirement_kind == "none"

    def test_second_run_is_a_no_op(self, workspace, project):
        _type(workspace, "Story", 2)
        nfr = _type(workspace, "NFR", 2)
        quality = _issue(workspace, project, "P95 < 2s", nfr)

        _run(workspace, apply=True)
        output = _run(workspace, apply=False)

        quality.refresh_from_db()
        assert quality.requirement_kind == "quality"
        assert "Nothing to converge" in output

    def test_does_not_reach_into_another_workspace(self, db, workspace, project, create_user):
        from plane.db.models import Workspace

        other = Workspace.objects.create(name="Other", slug="other-ws", owner=create_user)
        other_nfr = _type(other, "NFR", 2)
        other_project = Project.objects.create(
            name="Other", identifier="OTH", workspace=other, created_by=create_user
        )
        item = _issue(other, other_project, "Untouched", other_nfr)

        _type(workspace, "Story", 2)
        _run(workspace, apply=True)

        item.refresh_from_db()
        assert item.type_id == other_nfr.id
        assert item.requirement_kind == "none"
