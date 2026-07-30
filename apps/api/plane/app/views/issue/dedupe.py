# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Work items that look like the one being written.

Postgres trigram similarity over the title, not a vector store. The question being asked is
"has someone already filed this", which is a question about wording -- two people describing
the same bug reach for the same nouns. A semantic index would answer a different and larger
question at the cost of a new service to run, and this is a warning at creation time rather
than a search feature.

`pg_trgm` is created if absent, because a self-hosted deployment cannot be assumed to have
run anything by hand. Falling back to `icontains` rather than failing means the warning
degrades instead of the create form breaking.
"""

# Django imports
from django.db import ProgrammingError, connection
from django.db.utils import OperationalError

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import ProjectEntityPermission
from plane.app.views.base import BaseAPIView
from plane.db.models import Issue

# Below this the pairs stop being things a person would call duplicates.
SIMILARITY_FLOOR = 0.3
MAX_RESULTS = 5


class WorkItemDeDupeEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        name = (request.query_params.get("name") or "").strip()
        # Two words is where "add" or "fix bug" stops predicting anything.
        if len(name) < 5:
            return Response({"results": []}, status=status.HTTP_200_OK)

        exclude_id = request.query_params.get("exclude")
        base = Issue.issue_objects.filter(project_id=project_id, workspace__slug=slug)
        if exclude_id:
            base = base.exclude(pk=exclude_id)

        try:
            results = self._by_similarity(base, name)
        except (ProgrammingError, OperationalError):
            # No trigram extension and no permission to create one. A degraded warning is
            # better than a create form that 500s.
            results = [
                {"id": str(issue.id), "name": issue.name, "sequence_id": issue.sequence_id, "similarity": None}
                for issue in base.filter(name__icontains=name[:40])[:MAX_RESULTS]
            ]

        return Response({"results": results}, status=status.HTTP_200_OK)

    def _by_similarity(self, queryset, name):
        from django.contrib.postgres.search import TrigramSimilarity

        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

        rows = (
            queryset.annotate(similarity=TrigramSimilarity("name", name))
            .filter(similarity__gt=SIMILARITY_FLOOR)
            .order_by("-similarity")[:MAX_RESULTS]
        )
        return [
            {
                "id": str(issue.id),
                "name": issue.name,
                "sequence_id": issue.sequence_id,
                "similarity": round(issue.similarity, 3),
            }
            for issue in rows
        ]
