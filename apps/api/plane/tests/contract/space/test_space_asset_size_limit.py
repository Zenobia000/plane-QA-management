# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Contract tests for the ``FILE_SIZE_LIMIT`` clamp on published Space uploads.

Regression coverage for upstream #9242, cherry-picked into this fork.

``POST /api/public/assets/v2/anchor/{anchor}/`` trusted the client-supplied
``size`` end-to-end: it was persisted on the ``FileAsset`` and handed straight to
``generate_presigned_post()``, which uses it as the S3/MinIO policy bound
(``["content-length-range", 1, file_size]``). Any authenticated caller who could
reach a published board could therefore mint a signed upload policy above the
instance's ``FILE_SIZE_LIMIT``. The fix clamps to ``[1, FILE_SIZE_LIMIT]`` and
rejects non-integer input with a 400.

Upstream shipped the fix without tests; this file is the fork's own guard. It
asserts on the value reaching ``generate_presigned_post`` -- the policy bound is
what actually constrains the upload, so a fix that only sanitised the stored
metadata would still fail here.
"""

from unittest import mock

import pytest
from django.conf import settings
from rest_framework import status

from plane.db.models import DeployBoard, FileAsset, Project, ProjectMember

S3_STORAGE_PATH = "plane.space.views.asset.S3Storage"

OVERSIZED = settings.FILE_SIZE_LIMIT * 10


@pytest.fixture
def project(db, workspace, create_user):
    """A project in the fixture workspace; ``create_user`` is an active member."""
    project = Project.objects.create(
        name="Test Project",
        identifier="TP",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=20)
    return project


@pytest.fixture
def deploy_board(db, workspace, project, create_user):
    """A published board, which is what makes the public upload route reachable."""
    return DeployBoard.objects.create(
        entity_identifier=project.id,
        entity_name="project",
        workspace=workspace,
        project=project,
        created_by=create_user,
    )


def upload_url(anchor):
    return f"/api/public/assets/v2/anchor/{anchor}/"


def payload(size, **overrides):
    body = {
        "name": "poster.png",
        "type": "image/png",
        "size": size,
        "entity_type": FileAsset.EntityTypeContext.COMMENT_DESCRIPTION,
    }
    body.update(overrides)
    return body


@pytest.mark.contract
class TestSpaceAssetSizeLimit:
    """The signed upload policy must never exceed the instance file size limit."""

    @pytest.mark.django_db
    def test_oversized_size_is_clamped_in_presigned_policy(self, session_client, deploy_board):
        """A ``size`` above the limit must not widen the presigned policy bound."""
        with mock.patch(S3_STORAGE_PATH) as mock_storage:
            mock_storage.return_value.generate_presigned_post.return_value = {"url": "https://signed.example"}
            response = session_client.post(
                upload_url(deploy_board.anchor), payload(OVERSIZED), format="json"
            )

        assert response.status_code == status.HTTP_200_OK, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )
        _, kwargs = mock_storage.return_value.generate_presigned_post.call_args
        assert kwargs["file_size"] == settings.FILE_SIZE_LIMIT

    @pytest.mark.django_db
    def test_oversized_size_is_clamped_on_stored_asset(self, session_client, deploy_board):
        """The persisted asset metadata must record the clamped size, not the claim."""
        with mock.patch(S3_STORAGE_PATH) as mock_storage:
            mock_storage.return_value.generate_presigned_post.return_value = {"url": "https://signed.example"}
            response = session_client.post(
                upload_url(deploy_board.anchor), payload(OVERSIZED), format="json"
            )

        asset = FileAsset.objects.get(pk=response.data["asset_id"])
        assert asset.size == settings.FILE_SIZE_LIMIT
        assert asset.attributes["size"] == settings.FILE_SIZE_LIMIT

    @pytest.mark.django_db
    @pytest.mark.parametrize("claimed", [0, -1])
    def test_non_positive_size_is_clamped_to_one(self, session_client, deploy_board, claimed):
        """``content-length-range`` needs a positive upper bound to stay valid."""
        with mock.patch(S3_STORAGE_PATH) as mock_storage:
            mock_storage.return_value.generate_presigned_post.return_value = {"url": "https://signed.example"}
            response = session_client.post(
                upload_url(deploy_board.anchor), payload(claimed), format="json"
            )

        assert response.status_code == status.HTTP_200_OK, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )
        _, kwargs = mock_storage.return_value.generate_presigned_post.call_args
        assert kwargs["file_size"] == 1

    @pytest.mark.django_db
    def test_non_integer_size_is_rejected(self, session_client, deploy_board):
        """Malformed input must 400 rather than raise a 500 out of ``int()``."""
        with mock.patch(S3_STORAGE_PATH) as mock_storage:
            response = session_client.post(
                upload_url(deploy_board.anchor), payload("not-a-number"), format="json"
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )
        mock_storage.return_value.generate_presigned_post.assert_not_called()
        assert not FileAsset.objects.exists()

    @pytest.mark.django_db
    def test_size_within_limit_is_passed_through(self, session_client, deploy_board):
        """Positive control: the clamp must not shrink legitimate uploads."""
        legitimate = settings.FILE_SIZE_LIMIT // 2

        with mock.patch(S3_STORAGE_PATH) as mock_storage:
            mock_storage.return_value.generate_presigned_post.return_value = {"url": "https://signed.example"}
            response = session_client.post(
                upload_url(deploy_board.anchor), payload(legitimate), format="json"
            )

        assert response.status_code == status.HTTP_200_OK, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )
        _, kwargs = mock_storage.return_value.generate_presigned_post.call_args
        assert kwargs["file_size"] == legitimate
        assert FileAsset.objects.get(pk=response.data["asset_id"]).size == legitimate
