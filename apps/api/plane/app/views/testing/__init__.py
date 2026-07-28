# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from .capability import TestingCapabilityEndpoint
from .library import (
    TestCaseDetailEndpoint,
    TestCaseListCreateEndpoint,
    TestCaseVersionDetailEndpoint,
    TestCaseWorkItemLinkDetailEndpoint,
    TestCaseWorkItemLinkEndpoint,
    TestFolderDetailEndpoint,
    TestFolderListCreateEndpoint,
    TestLibraryCSVEndpoint,
)
from .run import (
    AppAutomationIngestionEndpoint,
    TestResultDefectEndpoint,
    TestRunCloseEndpoint,
    TestRunDetailEndpoint,
    TestRunListCreateEndpoint,
    TestRunResultEndpoint,
)
from .attachment import TestResultAttachmentEndpoint
from .report import (
    TestingOverviewEndpoint,
    TestingReleaseEvidenceEndpoint,
    TestingRequirementCoverageEndpoint,
)

__all__ = [
    "TestingCapabilityEndpoint",
    "TestCaseDetailEndpoint",
    "TestCaseListCreateEndpoint",
    "TestCaseVersionDetailEndpoint",
    "TestCaseWorkItemLinkDetailEndpoint",
    "TestCaseWorkItemLinkEndpoint",
    "TestFolderDetailEndpoint",
    "TestFolderListCreateEndpoint",
    "TestRunCloseEndpoint",
    "TestRunDetailEndpoint",
    "TestRunListCreateEndpoint",
    "TestRunResultEndpoint",
    "TestResultDefectEndpoint",
    "TestResultAttachmentEndpoint",
    "TestingOverviewEndpoint",
    "AppAutomationIngestionEndpoint",
    "TestLibraryCSVEndpoint",
    "TestingReleaseEvidenceEndpoint",
    "TestingRequirementCoverageEndpoint",
]
