# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""What the field reported, and what the team said about it.

The overview's frontline and noticeboard panels are both invisible until somebody has used
them: a project with no intake shows no frontline, and a project with no announcements shows
an empty board. That is the right behaviour in production and useless in a demo, where the
whole point is to see what the surfaces do.

So this module seeds one plausible week of that traffic -- five reports from three
accounts in different triage states, and three announcements filed under topics that are
not all engineering. Nothing here is required by the product; it exists so the panels have
something to say.

The account names are invented and the grouping property is created here rather than in
`scaffolding.PROPERTY_DEFINITIONS`, because it is the one property carrying
`is_grouping_dimension` and that flag is what the frontline panel keys off. Keeping it
beside the intake rows it explains means a reader of this file sees the whole mechanism at
once.
"""

from django.utils import timezone

from plane.db.models import (
    EntityUpdate,
    EntityUpdateLabel,
    Intake,
    IntakeIssue,
    Issue,
    IssueType,
    WorkItemProperty,
    WorkItemPropertyOption,
    WorkItemPropertyValue,
)

#: The dimension the overview groups intake by. Named in Chinese like the rest of the seed's
#: project-specific vocabulary, to make the point that no part of it is known to the code.
GROUPING_PROPERTY = "合作客戶"

ACCOUNTS = (
    ("acme", "Acme 物流"),
    ("northwind", "Northwind 零售"),
    ("globex", "Globex 製造"),
)

# `IntakeIssueStatus` values, spelled out so the seeded board shows all three answers the
# panel folds them into rather than a queue that is uniformly untriaged.
PENDING, ACCEPTED, REJECTED = -2, 1, -1

# (title, account values, status, what the report was about)
REPORTS = (
    (
        "月結報表匯出逾時,超過 5,000 筆就中斷",
        ["acme"],
        PENDING,
        "客戶月底結帳卡住,已影響三個分公司。",
    ),
    (
        "登入偶發失敗,重試一次就成功",
        ["acme", "northwind"],
        PENDING,
        "兩個客戶同一週回報,疑似同一個 session 問題。",
    ),
    (
        "希望訂單列表能記住上次的篩選條件",
        ["northwind"],
        ACCEPTED,
        "已排入下個 sprint,屬於體驗改善而非缺陷。",
    ),
    (
        "批次匯入的錯誤訊息看不懂是哪一列出錯",
        ["globex"],
        ACCEPTED,
        "已排入,順便補上行號與欄位名。",
    ),
    (
        "想要一個能自己設計欄位的報表產生器",
        ["globex"],
        REJECTED,
        "婉拒:超出這個產品的範圍,已建議改用既有的匯出加試算表。",
    ),
)

# (status, description, topic label names)
ANNOUNCEMENTS = (
    (
        "off_track",
        "Acme 月結報表匯出逾時已升級為 P1。結帳窗口在月底前四天,若這週未修完會影響對方三個分公司,"
        "業務已先口頭致歉。修法與時程今天下班前回覆。",
        ("客戶承諾",),
    ),
    (
        "on_track",
        "下季主打「批次作業可觀測性」。市場端希望在九月的產業展前有可展示的版本,"
        "所以匯入錯誤訊息與批次進度條這兩件會優先於既有技術債。",
        ("跨團隊相依",),
    ),
    (
        "at_risk",
        "金流團隊的稽核回寫介面延後兩週,我們這邊的驗收案例先擋著。若下週三前仍未收到接口文件,"
        "本季的法規稽核項目要重新評估範圍。",
        ("法規稽核", "跨團隊相依"),
    ),
)


def create_frontline(workspace, project, owner, labels):
    """Intake tagged by account, plus the announcements a team would post about it."""
    dimension = _create_dimension(workspace, project)
    intake = _project_intake(workspace, project, owner)
    bug_type = IssueType.objects.filter(workspace=workspace, name="Bug").first()

    reports = [
        _file_report(workspace, project, owner, intake, dimension, bug_type, report) for report in REPORTS
    ]
    announcements = _post_announcements(workspace, project, owner, labels)
    return {"dimension": dimension, "reports": reports, "announcements": announcements}


def _create_dimension(workspace, project):
    """The property the overview groups by. One per project, enforced by the database."""
    prop = WorkItemProperty.objects.create(
        project=project,
        workspace=workspace,
        name=GROUPING_PROPERTY,
        description="回報這件事的客戶。多選,因為同一個問題常常不只一家碰到。",
        kind=WorkItemProperty.Kind.MULTI_SELECT,
        is_grouping_dimension=True,
        sort_order=500,
    )
    for index, (value, label) in enumerate(ACCOUNTS):
        WorkItemPropertyOption.objects.create(
            property=prop,
            project=project,
            workspace=workspace,
            label=label,
            value=value,
            sort_order=(index + 1) * 1000,
        )
    return prop


def _project_intake(workspace, project, owner):
    """The project's intake. `create_project` may already have made one; reuse it."""
    intake = Intake.objects.filter(project=project).first()
    if intake:
        return intake
    return Intake.objects.create(
        workspace=workspace, project=project, name=f"{project.name} intake", created_by=owner, is_default=True
    )


def _file_report(workspace, project, owner, intake, dimension, bug_type, report):
    name, accounts, status, note = report
    issue = Issue.objects.create(
        workspace=workspace,
        project=project,
        name=name,
        description_html=f"<p>{note}</p>",
        type=bug_type,
        created_by=owner,
        # Priority is deliberately left at the default. Something arriving from outside the
        # team has not been triaged yet, and stamping one here would pretend it had.
    )
    WorkItemPropertyValue.objects.create(
        workspace=workspace, project=project, property=dimension, issue=issue, value=accounts
    )
    return IntakeIssue.objects.create(
        workspace=workspace,
        project=project,
        intake=intake,
        issue=issue,
        status=status,
        source="EMAIL",
        source_email="support@example.com",
        created_by=owner,
    )


def _post_announcements(workspace, project, owner, labels):
    """Three posts, only one of which is about engineering.

    That mix is the point. A noticeboard that only carries sprint status is a status thread
    under a different name; the reason to put topics on it is that a market deadline and a
    customer escalation belong on the same board as the release date they both move.
    """
    now = timezone.now()
    posted = []
    for index, (status, description, topic_names) in enumerate(ANNOUNCEMENTS):
        update = EntityUpdate.objects.create(
            workspace=workspace,
            project=project,
            entity_name=EntityUpdate.EntityName.PROJECT,
            entity_identifier=project.id,
            status=status,
            description=description,
            actor=owner,
            created_by=owner,
        )
        # Newest first in the panel, so the oldest post is backdated furthest.
        EntityUpdate.objects.filter(pk=update.pk).update(
            created_at=now - timezone.timedelta(days=len(ANNOUNCEMENTS) - index)
        )
        for topic_name in topic_names:
            topic = labels.get(topic_name)
            if topic:
                EntityUpdateLabel.objects.create(
                    workspace=workspace, project=project, entity_update=update, label=topic
                )
        posted.append(update)
    return posted
