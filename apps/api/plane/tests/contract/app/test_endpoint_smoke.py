# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Every project-scoped GET the browser can reach, asserted not to 500.

This exists because two endpoints returned 500 on every request and neither was noticed
for as long as they had existed. The cycle analytics view raised at query-compile time on
a mixed-type `Concat`, and the favourites list select_related a foreign key its model does
not have. Both were reachable, both were registered as if they worked, and neither had a
test -- the only reason anyone found the first one was a screenshot of a blank panel.

A blank panel is what a 500 looks like from the outside: the components render an empty
state when data is missing and say nothing about why. So the useful assertion is not that
a route returns the right shape -- each endpoint's own test covers that -- but that it
returns *anything* rather than blowing up.

4xx is fine and expected. A route may need a query parameter, may not accept GET, may
require a feature this project has switched off. What must never happen is 5xx.

Routes are discovered from the resolver rather than listed, so a new endpoint is covered
the day it is registered. Anything this cannot supply arguments for is reported by
`test_coverage_is_reported` instead of being dropped silently.
"""

import re

import pytest
from django.urls import get_resolver
from django.utils import timezone
from rest_framework import status

from plane.db.models import (
    Cycle,
    Issue,
    IssueAssignee,
    IssueLabel,
    Label,
    Module,
    Project,
    ProjectMember,
    State,
)

# Params this can fill in from the fixture. Anything else makes a route unprobeable,
# which `test_coverage_is_reported` prints rather than passing over.
#
# `cycle_id` and `module_id` are here deliberately: the analytics views that prompted this
# file hang off them, and a smoke test that cannot reach the endpoint it was written for
# is worse than none -- it reports confidence it has not earned.
FILLABLE = {"slug", "project_id", "cycle_id", "module_id", "issue_id", "work_item_id"}

# GET on these is genuinely expensive or writes to storage; covered by their own tests.
SKIP = {
    "testing/export/",
    "testing/test-cases.csv",
}

# Workspace-scoped GETs that already 500, found the hour the workspace-scoped pass below
# was added. Both are upstream registration mistakes, not fork code, and fixing them here
# would put two unrelated changes in a team-calendar branch -- guideline A1 is one branch,
# one thing.
#
#   file-assets/             `FileAssetEndpoint.get()` does not accept the `slug` its own
#                            URL passes, so GET has never worked on that registration.
#   user-favorite-projects/  `ProjectFavoritesViewSet` declares no `serializer_class`.
#
# Named rather than skipped so a third one fails the build instead of quietly joining
# them, and printed on every run so "the smoke test passes" cannot be read as "the
# surface is clean". Fixing one upstream does not break this list.
KNOWN_WORKSPACE_500 = {
    "api/workspaces/<str:slug>/file-assets/",
    "api/workspaces/<str:slug>/user-favorite-projects/",
}


def walk(resolver, prefix=""):
    """Every registered URL pattern, flattened to its full path string."""
    for pattern in resolver.url_patterns:
        path = prefix + str(pattern.pattern)
        if hasattr(pattern, "url_patterns"):
            yield from walk(pattern, path)
        else:
            yield path


def route_params(path):
    """Path converters are `<converter:name>` or bare `<name>`; re_path uses `(?P<name>...)`.

    Take the name in every form so nothing is misread as fillable.
    """
    return set(re.findall(r"<(?:\?P<)?(?:[a-z_]+:)?([a-zA-Z_]+)>", path))


def probeable_routes():
    """Every registered app-API route whose GET this fixture set can address."""
    routes = set()
    for path in walk(get_resolver()):
        if not path.startswith("api/workspaces/"):
            continue
        params = route_params(path)
        if params <= FILLABLE and "project_id" in params:
            routes.add(path)
    return sorted(routes)


def workspace_scoped_routes():
    """Every registered app-API route addressable with a workspace slug alone.

    `probeable_routes` requires `project_id`, so a surface that hangs off the workspace
    rather than a project -- availability is the first this fork adds -- would register and
    never be probed. Discovered separately rather than by relaxing that filter, because
    each assertion carries its own minimum count and merging them would let a collapse in
    one be masked by the other.
    """
    return sorted(
        path
        for path in walk(get_resolver())
        if path.startswith("api/workspaces/") and route_params(path) == {"slug"}
    )


@pytest.fixture
def populated_project(db, workspace, create_user):
    """A project with one of most things, so routes have rows to serialise.

    An empty project hides bugs: a queryset that would raise on a real row can return an
    empty list without ever evaluating the expression that breaks.
    """
    project = Project.objects.create(name="Smoke", identifier="SMOK", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20, is_active=True)
    state = State.objects.create(workspace=workspace, project=project, name="Doing", group="started", sequence=1000)
    label = Label.objects.create(workspace=workspace, project=project, name="urgent")
    now = timezone.now()
    cycle = Cycle.objects.create(
        workspace=workspace,
        project=project,
        name="Sprint",
        start_date=now - timezone.timedelta(days=3),
        end_date=now + timezone.timedelta(days=3),
        owned_by=create_user,
    )
    module = Module.objects.create(workspace=workspace, project=project, name="Module", created_by=create_user)
    issue = None
    for index in range(2):
        issue = Issue.objects.create(
            workspace=workspace,
            project=project,
            name=f"Item {index}",
            state=state,
            created_by=create_user,
        )
        # An assignee is what triggers the avatar annotation that used to raise. Built
        # explicitly rather than through `assignees.add`, which cannot set project_id.
        IssueAssignee.objects.create(workspace=workspace, project=project, issue=issue, assignee=create_user)
        IssueLabel.objects.create(workspace=workspace, project=project, issue=issue, label=label)
        cycle.issue_cycle.create(workspace=workspace, project=project, issue=issue, created_by=create_user)
        module.issue_module.create(workspace=workspace, project=project, issue=issue, created_by=create_user)
    return {"project": project, "cycle": cycle, "module": module, "issue": issue}


def fill(route, workspace, fixtures):
    """Substitute every parameter this route needs, whatever converter it declares."""
    ids = {
        "slug": workspace.slug,
        "project_id": str(fixtures["project"].id),
        "cycle_id": str(fixtures["cycle"].id),
        "module_id": str(fixtures["module"].id),
        "issue_id": str(fixtures["issue"].id),
        "work_item_id": str(fixtures["issue"].id),
    }
    filled = route
    for name, value in ids.items():
        filled = re.sub(rf"<(?:[a-z_]+:)?{name}>", value, filled)
    return "/" + filled


@pytest.mark.contract
@pytest.mark.django_db
def test_no_project_scoped_get_returns_a_server_error(session_client, workspace, populated_project):
    """The assertion that would have caught both bugs on the day they landed."""
    failures = []
    probed = 0

    for route in probeable_routes():
        if any(tail in route for tail in SKIP):
            continue
        url = fill(route, workspace, populated_project)
        probed += 1
        try:
            code = session_client.get(url).status_code
        except Exception as error:  # a view that raises past the handler is also a failure
            failures.append(f"{route} raised {type(error).__name__}: {error}")
            continue
        if code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            failures.append(f"{route} -> {code}")

    assert probed > 40, f"only {probed} routes probed; discovery is likely broken"
    assert not failures, "server errors:\n  " + "\n  ".join(failures)


@pytest.mark.contract
@pytest.mark.django_db
def test_no_workspace_scoped_get_returns_a_server_error(session_client, workspace, populated_project):
    """The same assertion for surfaces that hang off the workspace rather than a project.

    A project is created anyway: several workspace endpoints aggregate across projects, and
    an empty workspace hides the same class of bug an empty project does.
    """
    failures = []
    probed = 0

    for route in workspace_scoped_routes():
        if any(tail in route for tail in SKIP):
            continue
        url = fill(route, workspace, populated_project)
        probed += 1
        try:
            code = session_client.get(url).status_code
        except Exception as error:
            failures.append(f"{route} raised {type(error).__name__}: {error}")
            continue
        if code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            failures.append(f"{route} -> {code}")

    known = [f for f in failures if f.split(" -> ")[0] in KNOWN_WORKSPACE_500]
    unexpected = [f for f in failures if f not in known]

    if known:
        print("\npre-existing upstream 500s, still failing:\n  " + "\n  ".join(known))

    assert probed > 10, f"only {probed} workspace routes probed; discovery is likely broken"
    assert not unexpected, "new server errors:\n  " + "\n  ".join(unexpected)


@pytest.mark.contract
@pytest.mark.django_db
def test_the_availability_surface_is_probed():
    """The workspace-scoped pass exists because this fork added a workspace-scoped surface.

    Asserted by name so that deleting the discovery filter, or moving availability under a
    project, fails here rather than quietly dropping it from coverage.
    """
    assert any(route.endswith("availability/capabilities/") for route in workspace_scoped_routes())


@pytest.mark.contract
@pytest.mark.django_db
def test_the_routes_that_motivated_this_file_are_probed():
    """A smoke test that misses the bug it was written for is false confidence.

    The first draft of this file filled only slug and project_id, so
    `cycles/<cycle_id>/analytics/` -- the 500 that started all this -- was never reached
    and the suite passed with the bug reintroduced. These assertions stop that recurring.

    Modules have no analytics route; assuming symmetry with cycles is how the first
    version of this assertion failed.
    """
    routes = probeable_routes()

    assert any(route.endswith("/cycles/<uuid:cycle_id>/analytics/") for route in routes)
    assert any(route.endswith("/user-favorite-cycles/") for route in routes)
    assert any(route.endswith("/progress/") for route in routes)
    assert any(route.endswith("/overview/") for route in routes)


@pytest.mark.contract
@pytest.mark.django_db
def test_coverage_is_reported(capsys):
    """What this cannot reach, said out loud.

    Routes taking an entity id are not probed here; each has its own tests. Printing the
    count keeps the gap visible rather than letting "the smoke test passes" imply more
    coverage than there is.
    """
    app_routes = {p for p in walk(get_resolver()) if p.startswith("api/workspaces/")}
    probed = set(probeable_routes()) | set(workspace_scoped_routes())

    print(f"\nsmoke-probed {len(probed)} of {len(app_routes)} app API routes")
    print(f"not probed (need an entity id): {len(app_routes) - len(probed)}")

    assert probed, "no routes discovered at all"
