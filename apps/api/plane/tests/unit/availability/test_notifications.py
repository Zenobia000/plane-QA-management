# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Who hears about a leave request, and what the email is allowed to say.

The load-bearing test is `test_recipients_match_who_may_decide`. The task resolves
recipients by walking the same rule `may_decide` walks, in the opposite direction, and two
copies of one rule drift — so they are checked against each other rather than each against
a hand-written expectation.
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


def leave_for(workspace, member, status=LeaveStatus.PENDING, reason="", decided_by=None):
    return MemberLeave.objects.create(
        workspace=workspace,
        member=member,
        leave_type=LeaveType.objects.get_or_create(workspace=workspace, name="Annual")[0],
        start_date=MON,
        end_date=MON,
        status=status,
        reason=reason,
        decided_by=decided_by,
    )


def profile_for(workspace, member, approver=None):
    return MemberWorkProfile.objects.create(
        workspace=workspace,
        member=member,
        approver=approver,
        work_start_time=time(9, 0),
        work_end_time=time(18, 0),
    )


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
    def test_it_reaches_the_approver_with_the_reason(self, workspace, create_user, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        requester = add(workspace, "await-requester@plane.so")
        approver = add(workspace, "await-approver@plane.so")
        profile_for(workspace, requester, approver=approver)
        leave = leave_for(workspace, requester, reason="hospital appointment")

        sent = leave_awaiting_decision_email(str(leave.id), "http://localhost:8787")

        if sent:
            assert mail.outbox[0].to == [approver.email]
            # The approver is one of the two readers the serializer already trusts with it.
            assert "hospital appointment" in mail.outbox[0].alternatives[0][0]

    def test_a_decided_request_sends_nothing(self, workspace, create_user, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        requester = add(workspace, "await-decided@plane.so")
        leave = leave_for(workspace, requester, status=LeaveStatus.APPROVED)

        assert leave_awaiting_decision_email(str(leave.id), "http://localhost:8787") == 0

    def test_a_missing_leave_is_not_an_error(self):
        """A cancelled-then-purged row must not leave a task crashing in the worker forever."""
        assert leave_awaiting_decision_email("00000000-0000-0000-0000-000000000000", "http://x") == 0


@pytest.mark.unit
@pytest.mark.django_db
class TestDecidedEmail:
    def test_it_reaches_the_requester(self, workspace, create_user, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        requester = add(workspace, "decided-requester@plane.so")
        leave = leave_for(workspace, requester, status=LeaveStatus.APPROVED, decided_by=create_user)

        sent = leave_decided_email(str(leave.id), "http://localhost:8787")

        if sent:
            assert mail.outbox[0].to == [requester.email]

    def test_a_still_pending_request_sends_nothing(self, workspace, create_user, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        requester = add(workspace, "decided-pending@plane.so")
        leave = leave_for(workspace, requester)

        assert leave_decided_email(str(leave.id), "http://localhost:8787") == 0

    def test_a_cancelled_request_sends_nothing(self, workspace, create_user, settings):
        """Cancelling is the requester's own act; mailing them about it is noise."""
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        requester = add(workspace, "decided-cancelled@plane.so")
        leave = leave_for(workspace, requester, status=LeaveStatus.CANCELLED)

        assert leave_decided_email(str(leave.id), "http://localhost:8787") == 0
