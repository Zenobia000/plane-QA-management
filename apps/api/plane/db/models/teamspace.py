# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""A team that spans projects rather than living inside one.

`Team` has existed in `workspace.py` since long before this -- name, description, workspace,
logo and nothing else, referenced by nothing. It is reused rather than replaced: a second
table meaning the same thing would leave the first as a trap for whoever finds it next.

What was missing is the two edges that make a teamspace useful, which is membership and
which projects it covers. Both are workspace-scoped join tables, deliberately not
`ProjectBaseModel`: a teamspace that belonged to a project would be a module.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

from .base import BaseModel


class TeamMember(BaseModel):
    team = models.ForeignKey("db.Team", on_delete=models.CASCADE, related_name="members")
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="teams")
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="team_members")

    class Meta:
        verbose_name = "Team Member"
        verbose_name_plural = "Team Members"
        db_table = "team_members"
        constraints = [
            models.UniqueConstraint(
                fields=["team", "member"],
                condition=Q(deleted_at__isnull=True),
                name="team_member_unique_when_active",
            )
        ]

    def __str__(self):
        return f"{self.team} <- {self.member}"


class TeamProject(BaseModel):
    team = models.ForeignKey("db.Team", on_delete=models.CASCADE, related_name="projects")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="teams")
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="team_projects")

    class Meta:
        verbose_name = "Team Project"
        verbose_name_plural = "Team Projects"
        db_table = "team_projects"
        constraints = [
            models.UniqueConstraint(
                fields=["team", "project"],
                condition=Q(deleted_at__isnull=True),
                name="team_project_unique_when_active",
            )
        ]

    def __str__(self):
        return f"{self.team} -> {self.project}"
