# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Time logged against a work item.

Stored as whole minutes, matching `EstimateType.TIME`: a decimal of hours reads as 1.75h,
which is a number someone has to convert before acting on it, and summing thirds of an hour
is not exact.

`Project.is_time_tracking_enabled` already existed and was already serialised -- the flag
shipped years before anything could be logged against it. It now gates writes.

`logged_at` is a date rather than a timestamp because the question worklogs answer is "how
much on which day", and recording a clock time invites a precision the entry method does not
have.
"""

from django.conf import settings
from django.db import models

from .project import ProjectBaseModel


class Worklog(ProjectBaseModel):
    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="worklogs")
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="worklogs",
    )
    duration = models.PositiveIntegerField(help_text="Whole minutes.")
    description = models.TextField(blank=True)
    logged_at = models.DateField()

    class Meta:
        verbose_name = "Worklog"
        verbose_name_plural = "Worklogs"
        db_table = "worklogs"
        ordering = ("-logged_at", "-created_at")
        indexes = [models.Index(fields=["issue", "logged_at"], name="worklog_issue_date_idx")]

    def __str__(self):
        return f"{self.issue_id} {self.duration}m"
