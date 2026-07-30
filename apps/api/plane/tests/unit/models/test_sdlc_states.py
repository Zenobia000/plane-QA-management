# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The SDLC state set, checked against the four readers that key off `group`.

These are not shape tests. Every assertion below corresponds to a decision some other
module makes from the group a state belongs to, so a future edit that regroups a state has
to come here and state why the downstream consequence is acceptable.
"""

import pytest

from plane.db.models.state import SDLC_STATES, StateGroup

UNSCHEDULED_STATE_GROUPS = {"backlog", "cancelled"}

BY_NAME = {state["name"]: state for state in SDLC_STATES}


class TestSDLCStateSet:
    def test_names_are_unique(self):
        """`State` is unique on (name, project), so a duplicate would break bulk_create."""
        names = [state["name"] for state in SDLC_STATES]
        assert len(names) == len(set(names))

    def test_every_group_is_a_real_group(self):
        valid = {choice.value for choice in StateGroup}
        assert {state["group"] for state in SDLC_STATES} <= valid

    def test_sequences_are_strictly_increasing(self):
        """Board column order and `State.Meta.ordering` both read `sequence`."""
        sequences = [state["sequence"] for state in SDLC_STATES]
        assert sequences == sorted(sequences)
        assert len(sequences) == len(set(sequences))

    def test_exactly_one_default(self):
        """`Issue._ensure_default_state` picks `default=True`; two would make it arbitrary."""
        defaults = [state for state in SDLC_STATES if state.get("default")]
        assert [state["name"] for state in defaults] == ["Backlog"]

    def test_triage_state_exists(self):
        """Intake resolves a triage state even when the feature is off."""
        assert BY_NAME["Triage"]["group"] == StateGroup.TRIAGE.value


class TestGroupConsequences:
    """Each test names the module that would change behaviour if the grouping changed."""

    def test_wait_to_release_still_blocks_the_release_gate(self):
        """`report.py` counts a defect as open while its group is not completed/cancelled.

        Grouping `Wait to Release` as `completed` would stop a defect parked there from
        blocking the gate -- the gate would call a release ready while an unresolved defect
        sat in the column named for waiting to release.
        """
        assert BY_NAME["Wait to Release"]["group"] == StateGroup.STARTED.value

    def test_only_done_counts_as_delivered(self):
        """Cycle progress is `(completed + cancelled) / total`, so `completed` means shipped."""
        completed = [s["name"] for s in SDLC_STATES if s["group"] == StateGroup.COMPLETED.value]
        assert completed == ["Done"]

    def test_scheduled_states_owe_an_acceptance_contract(self):
        """Definition of Ready starts biting the moment work is committed to a sprint.

        `requirement_coverage` treats every group except backlog and cancelled as in scope.
        `Next Sprint` and `Todo` are the two commitment states, so both must sit in a group
        that is in scope, or the gate would stop reporting contract-less scheduled work.
        """
        for name in ("Next Sprint", "Todo"):
            assert BY_NAME[name]["group"] not in UNSCHEDULED_STATE_GROUPS

    def test_only_backlog_is_exempt_from_contracts(self):
        """Nothing else should be able to hide from the coverage denominator."""
        exempt = [s["name"] for s in SDLC_STATES if s["group"] in UNSCHEDULED_STATE_GROUPS]
        assert sorted(exempt) == ["Backlog", "Canceled"]

    def test_the_qa_handoff_is_visible_as_distinct_states(self):
        """The point of the set: eleven process stages stop collapsing into one column."""
        for name in ("PR Reviewing", "In Diversity Testing", "PM Retest"):
            assert BY_NAME[name]["group"] == StateGroup.STARTED.value

    def test_standing_work_is_not_modelled_as_a_state(self):
        """`Resident` and `Archived` describe kind and storage, not progress.

        `Resident` is carried as a label by the seed; `Archived` already exists as
        `Issue.archived_at` plus the archive views. A state of either name would give one
        concept two homes and, for `Resident`, distort every burndown it appeared in.
        """
        assert "Resident" not in BY_NAME
        assert "Archived" not in BY_NAME


@pytest.mark.django_db
class TestSeededProjectUsesTheSet:
    def test_shop_floor_seed_creates_the_sdlc_states(self, workspace, create_user):
        from plane.testing.demo import scaffolding

        project = scaffolding.create_project(workspace, create_user, "SDLC")

        # `State.objects` hides triage, so compare against the non-triage definitions.
        expected = {s["name"] for s in SDLC_STATES if s["group"] != StateGroup.TRIAGE.value}
        assert set(project.project_state.values_list("name", flat=True)) == expected

    def test_states_are_addressable_by_name_not_group(self, workspace, create_user):
        """Nine states share the `started` group, so a group-keyed lookup is ambiguous.

        The seed used to build `{state.group: state}`. This asserts the ambiguity is real,
        which is why `demo/__init__.py` keys by name instead.
        """
        from plane.testing.demo import scaffolding

        project = scaffolding.create_project(workspace, create_user, "SDLC2")

        started = project.project_state.filter(group=StateGroup.STARTED.value)
        assert started.count() > 1
