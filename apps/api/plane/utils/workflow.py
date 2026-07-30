# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Whether a state change is allowed, and by whom.

The rule is scoped to the *source* state, not to the project. A state that nobody has written
a transition out of is unconstrained; a state that has any transition out of it permits only
those. That is what lets a workflow be adopted one state at a time rather than all at once,
and it is why an existing project -- which has no rows at all -- keeps working unchanged.

Approval is the second gate and only applies to an edge that exists. A transition marked
`requires_approval` with no approvers listed is refused for everyone, because a rule that
nobody can satisfy is more likely a half-finished configuration than an intention, and
failing loudly is the only way anyone finds out.
"""

from plane.db.models import StateTransition


def transition_violation(project_id, from_state_id, to_state_id, actor_id):
    """The reason this state change cannot be made, or None when it can.

    `from_state_id` may be None -- a work item being created has no previous state, and
    creation is not a transition.
    """
    if from_state_id is None or to_state_id is None:
        return None
    if str(from_state_id) == str(to_state_id):
        return None

    outgoing = list(
        StateTransition.objects.filter(project_id=project_id, from_state_id=from_state_id).prefetch_related(
            "approvers"
        )
    )
    if not outgoing:
        # Nobody has constrained this state, so nothing is refused from it.
        return None

    edge = next((item for item in outgoing if str(item.to_state_id) == str(to_state_id)), None)
    if edge is None:
        return "This state change is not allowed by the project's workflow."

    if not edge.requires_approval:
        return None

    approver_ids = {str(approver.member_id) for approver in edge.approvers.all()}
    if not approver_ids:
        return "This state change requires approval, but no approvers are configured."
    if str(actor_id) not in approver_ids:
        return "This state change requires approval from a designated approver."
    return None
