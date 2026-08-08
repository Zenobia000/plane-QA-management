# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Who hears about a leave request, and what the email is allowed to say.

The load-bearing test is `test_recipients_match_who_may_decide`. The task resolves
recipients by walking the same rule `may_decide` walks, in the opposite direction, and two
copies of one rule drift — so they are checked against each other rather than each against
a hand-written expectation.

Everything that asserts about a sent message takes the `smtp` fixture. `_send` reads its
host from the instance configuration rather than from Django settings, and a test database
has none — so an assertion left outside that fixture is not a weak test, it is an
unreachable one, and the whole send path goes unwalked while the file reports green.
"""

from datetime import time

import pytest
from django.core import mail

from plane.availability import may_decide
from plane.bgtasks.availability_notification_task import (
    _recipients_for_decision,
    leave_awaiting_decision_email,
    leave_decided_email,
)
from plane.db.models import (
    LeaveStatus,
    LeaveType,
    MemberLeave,
    MemberWorkProfile,
    User,
    WorkspaceMember,
)

ADMIN = 20
MEMBER = 15
MON = "2026-08-03"


def add(workspace, email, role=MEMBER):
    user = User.objects.create(email=email, username=email.split("@")[0], display_name=email.split("@")[0])
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role, is_active=True)
    return user


def leave_for(workspace, member, status=LeaveStatus.PENDING, reason="", decided_by=None, decision_note=""):
    return MemberLeave.objects.create(
        workspace=workspace,
        member=member,
        leave_type=LeaveType.objects.get_or_create(workspace=workspace, name="Annual")[0],
        start_date=MON,
        end_date=MON,
        status=status,
        reason=reason,
        decided_by=decided_by,
        decision_note=decision_note,
    )


def profile_for(workspace, member, approver=None):
    return MemberWorkProfile.objects.create(
        workspace=workspace,
        member=member,
        approver=approver,
        work_start_time=time(9, 0),
        work_end_time=time(18, 0),
    )


def configure_mail(settings, monkeypatch, host="smtp.test"):
    """Point the task at a mail server that exists only in memory."""
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    monkeypatch.setattr(
        "plane.bgtasks.availability_notification_task.get_email_configuration",
        lambda: (host, "postbox", "secret", "587", "1", "0", "Plane <team@plane.test>"),
    )


@pytest.fixture
def smtp(settings, monkeypatch):
    """An instance whose mail is configured, which is the only case that sends anything.

    `get_email_configuration` reads the instance configuration table, which a test database
    never has a row in, so unpatched it hands back an empty host and `_send` returns before
    it renders a template. Django's `EMAIL_BACKEND` alone does not reach that check.
    """
    configure_mail(settings, monkeypatch)


@pytest.mark.unit
@pytest.mark.django_db
class TestRecipients:
    def test_a_named_approver_is_the_only_recipient(self, workspace, create_user):
        requester = add(workspace, "notify-requester@plane.so")
        approver = add(workspace, "notify-approver@plane.so")
        profile_for(workspace, requester, approver=approver)

        assert [u.id for u in _recipients_for_decision(leave_for(workspace, requester))] == [approver.id]

    def test_admins_are_the_fallback_when_nobody_is_named(self, workspace, create_user):
        requester = add(workspace, "notify-unnamed@plane.so")

        recipients = _recipients_for_decision(leave_for(workspace, requester))

        assert create_user.id in {u.id for u in recipients}

    def test_a_deactivated_approver_falls_back_to_admins(self, workspace, create_user):
        """Same hole the decision path had: nobody hears, nobody can act."""
        requester = add(workspace, "notify-stranded@plane.so")
        approver = add(workspace, "notify-gone@plane.so")
        profile_for(workspace, requester, approver=approver)
        WorkspaceMember.objects.filter(workspace=workspace, member=approver).update(is_active=False)

        recipients = _recipients_for_decision(leave_for(workspace, requester))

        assert approver.id not in {u.id for u in recipients}
        assert create_user.id in {u.id for u in recipients}

    def test_the_requester_never_receives_their_own_request(self, workspace, create_user):
        """An admin filing their own leave must not be asked to decide it."""
        recipients = _recipients_for_decision(leave_for(workspace, create_user))

        assert create_user.id not in {u.id for u in recipients}

    @pytest.mark.parametrize("named", [True, False])
    def test_recipients_match_who_may_decide(self, workspace, create_user, named):
        """The two copies of the approver rule, checked against each other.

        `may_decide` answers "may this actor decide"; the task asks "who may". If one grows a
        condition the other lacks, somebody is emailed who cannot act, or nobody is emailed at
        all — both silent.
        """
        requester = add(workspace, f"notify-parity-{named}@plane.so")
        approver = add(workspace, f"notify-parity-approver-{named}@plane.so")
        profile_for(workspace, requester, approver=approver if named else None)
        leave = leave_for(workspace, requester)

        for user in _recipients_for_decision(leave):
            assert may_decide(leave=leave, actor=user) is True


@pytest.mark.unit
@pytest.mark.django_db
class TestAwaitingDecisionEmail:
    def test_it_reaches_the_approver_with_the_reason(self, workspace, create_user, smtp):
        requester = add(workspace, "await-requester@plane.so")
        approver = add(workspace, "await-approver@plane.so")
        profile_for(workspace, requester, approver=approver)
        leave = leave_for(workspace, requester, reason="hospital appointment")

        assert leave_awaiting_decision_email(str(leave.id), "http://localhost:8787") == 1

        message = mail.outbox[0]
        assert message.to == [approver.email]
        assert message.subject == "await-requester asked for annual"
        # The approver is one of the two readers the serializer already trusts with it.
        assert "hospital appointment" in message.alternatives[0][0]
        # And in the plain-text part, which is what a client with HTML off shows.
        assert "hospital appointment" in message.body
        # The link has to land on the queue, not on the host root.
        assert f"http://localhost:8787/{workspace.slug}/calendar/leave" in message.alternatives[0][0]

    def test_each_admin_gets_their_own_copy(self, workspace, create_user, smtp):
        """One message per recipient. A shared To would tell each admin who else was asked."""
        requester = add(workspace, "await-fanout@plane.so")
        other_admin = add(workspace, "await-second-admin@plane.so", role=ADMIN)
        leave = leave_for(workspace, requester)

        assert leave_awaiting_decision_email(str(leave.id), "http://localhost:8787") == 2

        assert {message.to[0] for message in mail.outbox} == {create_user.email, other_admin.email}
        assert all(len(message.to) == 1 for message in mail.outbox)

    def test_an_instance_with_no_mail_server_sends_nothing(self, workspace, create_user, settings, monkeypatch):
        """A fresh install has no SMTP, and a leave nobody can be emailed about is still a leave.

        This is the branch every other run of this file takes, so it is the one that has to
        be named: reaching it must be a decision the code makes, not the accident of a test
        database having no configuration row.
        """
        configure_mail(settings, monkeypatch, host="")
        requester = add(workspace, "await-nosmtp@plane.so")
        leave = leave_for(workspace, requester)

        assert leave_awaiting_decision_email(str(leave.id), "http://localhost:8787") == 0
        assert mail.outbox == []

    def test_a_mail_server_that_refuses_does_not_raise(self, workspace, create_user, smtp, monkeypatch):
        """The request was already filed. A dead SMTP host must not turn that into a 500."""

        def refuse(**kwargs):
            raise OSError("connection refused")

        monkeypatch.setattr("plane.bgtasks.availability_notification_task.get_connection", refuse)
        requester = add(workspace, "await-refused@plane.so")
        leave = leave_for(workspace, requester)

        assert leave_awaiting_decision_email(str(leave.id), "http://localhost:8787") == 0
        assert mail.outbox == []

    def test_a_decided_request_sends_nothing(self, workspace, create_user, smtp):
        requester = add(workspace, "await-decided@plane.so")
        leave = leave_for(workspace, requester, status=LeaveStatus.APPROVED)

        assert leave_awaiting_decision_email(str(leave.id), "http://localhost:8787") == 0
        assert mail.outbox == []

    def test_a_missing_leave_is_not_an_error(self):
        """A cancelled-then-purged row must not leave a task crashing in the worker forever."""
        assert leave_awaiting_decision_email("00000000-0000-0000-0000-000000000000", "http://x") == 0


@pytest.mark.unit
@pytest.mark.django_db
class TestDecidedEmail:
    def test_it_reaches_the_requester(self, workspace, create_user, smtp):
        requester = add(workspace, "decided-requester@plane.so")
        leave = leave_for(workspace, requester, status=LeaveStatus.APPROVED, decided_by=create_user)

        assert leave_decided_email(str(leave.id), "http://localhost:8787") == 1

        message = mail.outbox[0]
        assert message.to == [requester.email]
        assert message.subject == "Your annual was approved"
        assert "approved" in message.body
        assert create_user.display_name in message.body

    def test_a_decline_says_declined_and_carries_the_note(self, workspace, create_user, smtp):
        """Approved and declined are one template with a branch, so both need walking.

        The note is the only place the decision's reasoning reaches the person it landed on;
        a template change that drops it turns a refusal into an unexplained one.
        """
        requester = add(workspace, "decided-declined@plane.so")
        leave = leave_for(
            workspace,
            requester,
            status=LeaveStatus.REJECTED,
            decided_by=create_user,
            decision_note="Two people are already away that week",
        )

        assert leave_decided_email(str(leave.id), "http://localhost:8787") == 1

        message = mail.outbox[0]
        assert message.subject == "Your annual was declined"
        assert "declined" in message.body
        assert "Two people are already away that week" in message.alternatives[0][0]

    def test_a_still_pending_request_sends_nothing(self, workspace, create_user, smtp):
        requester = add(workspace, "decided-pending@plane.so")
        leave = leave_for(workspace, requester)

        assert leave_decided_email(str(leave.id), "http://localhost:8787") == 0
        assert mail.outbox == []

    def test_a_cancelled_request_sends_nothing(self, workspace, create_user, smtp):
        """Cancelling is the requester's own act; mailing them about it is noise."""
        requester = add(workspace, "decided-cancelled@plane.so")
        leave = leave_for(workspace, requester, status=LeaveStatus.CANCELLED)

        assert leave_decided_email(str(leave.id), "http://localhost:8787") == 0
        assert mail.outbox == []
