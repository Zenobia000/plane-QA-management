# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Which state changes are legal, and who has to agree to them.

Modelled as an allow-list of edges rather than a deny-list, because the interesting property
of a workflow is the small set of moves it permits, not the large set it forbids. A project
with no rows here has no workflow and every transition is legal -- which is what every
existing project is, so switching the feature on cannot retroactively invalidate anything.

`StateTransition` is one directed edge. Its absence means "not allowed" only once the state
it leaves from has *any* edge defined; a state nobody has written a rule for is unconstrained.
That is the rule that lets a workflow be adopted a state at a time instead of all at once,
and it is the reason enforcement asks about the source state rather than about the project.

`StateTransitionApprover` is who may make a transition that needs approval. Empty means the
transition is legal for anyone the ordinary permission check already admits.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

from .project import ProjectBaseModel


class StateTransition(ProjectBaseModel):
    """One legal move between two states."""

    from_state = models.ForeignKey("db.State", on_delete=models.CASCADE, related_name="transitions_out")
    to_state = models.ForeignKey("db.State", on_delete=models.CASCADE, related_name="transitions_in")
    # When true the move is refused unless the actor is an approver of this transition.
    requires_approval = models.BooleanField(default=False)

    class Meta:
        verbose_name = "State Transition"
        verbose_name_plural = "State Transitions"
        db_table = "state_transitions"
        ordering = ("from_state", "to_state")
        constraints = [
            models.UniqueConstraint(
                fields=["project", "from_state", "to_state"],
                condition=Q(deleted_at__isnull=True),
                name="state_transition_unique_edge_when_active",
            )
        ]

    def __str__(self):
        return f"{self.from_state} -> {self.to_state}"


class StateTransitionApprover(ProjectBaseModel):
    """A member who may make a transition that requires approval."""

    transition = models.ForeignKey(StateTransition, on_delete=models.CASCADE, related_name="approvers")
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="state_transition_approvals",
    )

    class Meta:
        verbose_name = "State Transition Approver"
        verbose_name_plural = "State Transition Approvers"
        db_table = "state_transition_approvers"
        constraints = [
            models.UniqueConstraint(
                fields=["transition", "member"],
                condition=Q(deleted_at__isnull=True),
                name="state_transition_approver_unique_when_active",
            )
        ]

    def __str__(self):
        return f"{self.transition} <- {self.member}"
