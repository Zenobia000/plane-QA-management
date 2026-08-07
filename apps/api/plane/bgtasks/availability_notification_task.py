# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Email for the two moments in a leave request nobody is watching for.

Not the in-app inbox. `NotificationViewSet` filters `entity_name="issue"` and the card it
renders opens an issue peek overview on click, so a leave notification put through there
would be created, never listed, and broken if it were. Widening both is upstream surgery on
a component whose whole shape is a work item; email carries the two events without it.

Two events, and only two:

* a request needs deciding -> the person who can decide it
* it was decided -> the person who asked

The "waiting on you" queue already answers "what must I decide" for someone who opens the
page. What it cannot do is reach a person who is not looking, which is the entire job here.

ADR 0008 bounds what may go in these. `reason` reaches only the approver and the requester,
the two readers the serializer already allows; there is no digest, no per-person history,
and nothing that reports what anybody was observed doing.
"""

import logging

from celery import shared_task
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string

from plane.db.models import LeaveStatus, MemberLeave, MemberWorkProfile, User
from plane.license.utils.instance_value import get_email_configuration
from plane.utils.email import generate_plain_text_from_html
from plane.utils.exception_logger import log_exception

ADMIN = 20


def _recipients_for_decision(leave):
    """Who can act on this request, which is who should hear about it.

    Mirrors `plane.availability.services.may_decide` rather than importing it: that takes an
    actor and answers yes/no, and this needs the other direction. The rule is the same one --
    the named approver while they are still active, otherwise every workspace admin -- and
    the two must not drift, so a contract test pins them together.
    """
    approver_id = (
        MemberWorkProfile.objects.filter(workspace_id=leave.workspace_id, member_id=leave.member_id)
        .values_list("approver_id", flat=True)
        .first()
    )
    if approver_id:
        approver = User.objects.filter(
            pk=approver_id,
            member_workspace__workspace_id=leave.workspace_id,
            member_workspace__is_active=True,
        ).first()
        if approver:
            return [approver]

    return list(
        User.objects.filter(
            member_workspace__workspace_id=leave.workspace_id,
            member_workspace__role=ADMIN,
            member_workspace__is_active=True,
        ).exclude(pk=leave.member_id)
    )


def _send(subject, template, context, recipients):
    """Render and send, or log and give up.

    A workspace with no SMTP configured is the normal case on a fresh instance, and a leave
    that cannot be emailed about is still a valid leave -- so this never raises into the
    request that triggered it.
    """
    if not recipients:
        return 0

    try:
        (
            EMAIL_HOST,
            EMAIL_HOST_USER,
            EMAIL_HOST_PASSWORD,
            EMAIL_PORT,
            EMAIL_USE_TLS,
            EMAIL_USE_SSL,
            EMAIL_FROM,
        ) = get_email_configuration()

        if not EMAIL_HOST:
            logging.getLogger("plane.worker").info("Email not configured; skipping leave notification.")
            return 0

        html = render_to_string(template, context)
        text = generate_plain_text_from_html(html)

        connection = get_connection(
            host=EMAIL_HOST,
            port=int(EMAIL_PORT),
            username=EMAIL_HOST_USER,
            password=EMAIL_HOST_PASSWORD,
            use_tls=EMAIL_USE_TLS == "1",
            use_ssl=EMAIL_USE_SSL == "1",
        )

        sent = 0
        for recipient in recipients:
            if not recipient.email:
                continue
            message = EmailMultiAlternatives(
                subject=subject,
                body=text,
                from_email=EMAIL_FROM,
                to=[recipient.email],
                connection=connection,
            )
            message.attach_alternative(html, "text/html")
            message.send()
            sent += 1
        return sent
    except Exception as error:  # noqa: BLE001 - a failed email must not fail the decision
        log_exception(error)
        return 0


def _dates(leave):
    if leave.start_date == leave.end_date:
        return str(leave.start_date)
    return f"{leave.start_date} – {leave.end_date}"


@shared_task
def leave_awaiting_decision_email(leave_id, current_site):
    """Tell whoever can decide that something is waiting."""
    try:
        leave = MemberLeave.objects.select_related("workspace", "member", "leave_type").get(pk=leave_id)
    except MemberLeave.DoesNotExist:
        return 0

    if leave.status != LeaveStatus.PENDING:
        return 0

    requester = leave.member.display_name or leave.member.email
    return _send(
        subject=f"{requester} asked for {leave.leave_type.name.lower()}",
        template="emails/notifications/leave-awaiting-decision.html",
        context={
            "requester": requester,
            "leave_type": leave.leave_type.name,
            "dates": _dates(leave),
            # Only sent to a reader the serializer already trusts with it.
            "reason": leave.reason,
            "workspace_name": leave.workspace.name,
            "queue_url": f"{current_site}/{leave.workspace.slug}/calendar/leave",
        },
        recipients=_recipients_for_decision(leave),
    )


@shared_task
def leave_decided_email(leave_id, current_site):
    """Tell the person who asked. Without this they have to go and look."""
    try:
        leave = MemberLeave.objects.select_related("workspace", "member", "leave_type", "decided_by").get(
            pk=leave_id
        )
    except MemberLeave.DoesNotExist:
        return 0

    if leave.status not in (LeaveStatus.APPROVED, LeaveStatus.REJECTED):
        return 0

    approved = leave.status == LeaveStatus.APPROVED
    decider = leave.decided_by.display_name or leave.decided_by.email if leave.decided_by else "A workspace admin"

    return _send(
        subject=f"Your {leave.leave_type.name.lower()} was {'approved' if approved else 'declined'}",
        template="emails/notifications/leave-decided.html",
        context={
            "approved": approved,
            "leave_type": leave.leave_type.name,
            "dates": _dates(leave),
            "decider": decider,
            "note": leave.decision_note,
            "workspace_name": leave.workspace.name,
            "calendar_url": f"{current_site}/{leave.workspace.slug}/calendar/leave",
        },
        recipients=[leave.member],
    )
