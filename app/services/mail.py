"""Outbound mail for verification and password-reset links.

Defaults to the console backend so the whole auth flow is testable offline:
the message, including the link, is printed to stdout.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

log = logging.getLogger("nirvaan.mail")


def send(*, to: str, subject: str, body: str) -> bool:
    """Deliver a plain-text mail. Returns False on failure without raising."""
    if settings.mail_backend == "console" or not settings.smtp_host:
        # Development path: print instead of sending.
        print("\n" + "=" * 68)
        print(f"[NIRVAAN mail -> {to}]")
        print(f"Subject: {subject}")
        print("-" * 68)
        print(body)
        print("=" * 68 + "\n", flush=True)
        return True

    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
        return True
    except Exception as exc:  # noqa: BLE001 - mail must never break a request
        log.warning("mail delivery failed for %s: %s", to, exc)
        return False


def send_verification(*, to: str, name: str, link: str) -> bool:
    return send(
        to=to,
        subject="Confirm your NIRVAAN email address",
        body=(
            f"Hello {name},\n\n"
            "Please confirm your email address to finish setting up NIRVAAN:\n\n"
            f"{link}\n\n"
            "This link expires in 24 hours. If you did not create an account, "
            "you can ignore this message.\n\n"
            "NIRVAAN never asks for your password, OTP, PIN or bank details.\n"
        ),
    )


def send_password_reset(*, to: str, name: str, link: str) -> bool:
    return send(
        to=to,
        subject="Reset your NIRVAAN password",
        body=(
            f"Hello {name},\n\n"
            "You can set a new password using the link below:\n\n"
            f"{link}\n\n"
            "This link expires in 60 minutes and can be used once.\n"
            "If you did not request this, no action is needed - your current "
            "password still works.\n\n"
            "NIRVAAN never asks for your password, OTP, PIN or bank details.\n"
        ),
    )


def send_family_invitation(*, to: str, inviter: str, link: str, scopes: list[str]) -> bool:
    scope_lines = "\n".join(f"  - {s}" for s in scopes) or "  - (none requested)"
    return send(
        to=to,
        subject=f"{inviter} invited you to help on NIRVAAN",
        body=(
            f"Hello,\n\n{inviter} would like your help understanding financial "
            "information on NIRVAAN.\n\n"
            "If you accept, you would be able to see only:\n"
            f"{scope_lines}\n\n"
            "You will not be able to see anything else, and access can be "
            "withdrawn at any time.\n\n"
            f"{link}\n\n"
            "This invitation expires in 7 days.\n"
        ),
    )
