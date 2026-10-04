"""Audit and system-event recording.

``record`` never receives private user content - callers pass identifiers and
counts, not journal text, memories or transcripts.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session as DbSession

from app.models.system import AuditLog, SystemEvent

# Keys that must never reach the audit detail blob.
_BANNED_KEYS = {
    "password",
    "password_hash",
    "token",
    "otp",
    "pin",
    "card",
    "cvv",
    "account_number",
    "secret",
    "authorization",
}


def _scrub(detail: dict[str, Any] | None) -> dict[str, Any] | None:
    if not detail:
        return None
    clean: dict[str, Any] = {}
    for key, value in detail.items():
        if any(bad in key.lower() for bad in _BANNED_KEYS):
            clean[key] = "[redacted]"
        elif isinstance(value, str) and len(value) > 500:
            clean[key] = value[:500] + "...[truncated]"
        else:
            clean[key] = value
    return clean


def record(
    db: DbSession,
    *,
    action: str,
    user_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    outcome: str = "success",
    request: Request | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditLog:
    ip = user_agent = None
    if request is not None:
        forwarded = request.headers.get("x-forwarded-for", "")
        ip = (
            forwarded.split(",")[0].strip()
            if forwarded
            else (request.client.host if request.client else None)
        )
        user_agent = (request.headers.get("user-agent") or "")[:255] or None

    row = AuditLog(
        action=action,
        user_id=user_id,
        actor_user_id=actor_user_id,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        outcome=outcome,
        ip_address=ip,
        user_agent=user_agent,
        detail=_scrub(detail),
    )
    db.add(row)
    return row


def system_event(
    db: DbSession,
    *,
    component: str,
    event: str,
    level: str = "info",
    message: str = "",
    duration_ms: int | None = None,
    detail: dict[str, Any] | None = None,
) -> SystemEvent:
    row = SystemEvent(
        component=component,
        event=event,
        level=level,
        message=message[:2000],
        duration_ms=duration_ms,
        detail=_scrub(detail),
    )
    db.add(row)
    return row
