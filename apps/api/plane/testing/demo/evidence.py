# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Quality evidence that cannot be produced by running a test before shipping.

Availability is last month's measurement. A dependency scan belongs to the pipeline, not
to a tester. An architecture sign-off is a decision somebody makes. None of the three can
be executed on demand against a release candidate, so forcing them into the case library
produces contracts that are "executed" daily without any execution having occurred.

They are recorded as release evidence instead, and the gate reads them beside the run
results. That keeps one property the demo depends on: every test case in the library
corresponds to something a person or a pipeline actually ran.
"""

# Module imports
from plane.db.models import ReleaseEvidence, TestAutomationIngestion

# (kind, key, name, status, detail, source url)
RELEASE_EVIDENCE = (
    ("slo", "availability-monthly", "可用性(上月)", "failing",
     "99.7%,低於 99.9% 目標", "https://grafana.internal/slo/trace-query"),
    ("slo", "rpo-rto", "災難復原演練", "passing",
     "RPO 12 分鐘 / RTO 1 小時 40 分,符合目標", ""),
    ("scan", "dependency-audit", "相依套件稽核", "passing", "0 個高風險漏洞", ""),
    ("scan", "tls-baseline", "傳輸加密基線", "passing", "全數端點為 TLS 1.3", ""),
    ("review", "arch-signoff", "架構審查簽核", "pending", "等待平台組簽核", ""),
)


def record_release_evidence(workspace, project, owner):
    for kind, key, name, status, detail, url in RELEASE_EVIDENCE:
        ReleaseEvidence.objects.create(
            project=project, workspace=workspace, kind=kind, key=key, name=name,
            status=status, detail=detail, source_url=url, created_by=owner,
        )


def record_ingestion(project, run, owner):
    """The receipt CI leaves behind when it uploads results.

    The idempotency key is the whole mechanism: a pipeline that retries after a network
    failure sends the same key, and the second upload is recognised as a replay rather than
    creating a duplicate run. Without the receipt there is no way to tell a retry from a
    genuine second execution, and the sprint ends up with two runs claiming to be the same
    build.
    """
    return TestAutomationIngestion.objects.create(
        project=project,
        workspace=project.workspace,
        source="github-actions",
        idempotency_key=f"ci-{run.build}-regression",
        payload_hash="9f2c1d7a4b8e05c3a61d9f4e2b7c08a5d3e6f1b940c72a8e5d1f3b6c90a4e7d2",
        test_run=run,
        diagnostics=[
            {"level": "info", "message": "11 results mapped to existing contracts by external_id"},
            {"level": "warning", "message": "0 unmapped results; no orphan cases created"},
        ],
        created_by=owner,
    )
