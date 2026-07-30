# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Applying automation rules to a work item that has just changed state.

Called after the write, not during it, and it writes fields directly rather than going back
through the update path. That is what makes a loop impossible: an action can never be the
thing that triggers another rule. It is a structural property, not a depth counter, which is
why the action set is fixed rather than an expression language.
"""

from plane.db.models import Automation, IssueAssignee, IssueLabel

APPLICABLE_FIELDS = ("priority",)


def apply_automations(issue, previous_state_group, actor):
    """Run every active rule whose trigger group the item has just entered.

    Returns the names of the rules that fired, which is what the caller records. A rule whose
    action names something deleted is skipped rather than raised, because a project that has
    been tidied should not start failing every save.
    """
    new_group = issue.state.group if issue.state else None
    if not new_group or new_group == previous_state_group:
        return []

    rules = Automation.objects.filter(project_id=issue.project_id, is_active=True, trigger_state_group=new_group)

    fired = []
    for rule in rules:
        actions = rule.actions if isinstance(rule.actions, dict) else {}
        changed = {key: actions[key] for key in APPLICABLE_FIELDS if actions.get(key) is not None}
        if changed:
            for key, value in changed.items():
                setattr(issue, key, value)
            issue.save(update_fields=list(changed))

        for assignee_id in actions.get("assignee_ids", []) or []:
            IssueAssignee.objects.get_or_create(
                issue=issue,
                assignee_id=assignee_id,
                defaults={"project_id": issue.project_id, "workspace_id": issue.workspace_id, "created_by": actor},
            )
        for label_id in actions.get("label_ids", []) or []:
            IssueLabel.objects.get_or_create(
                issue=issue,
                label_id=label_id,
                defaults={"project_id": issue.project_id, "workspace_id": issue.workspace_id, "created_by": actor},
            )

        fired.append(rule.name)

    return fired
