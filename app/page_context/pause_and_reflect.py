"""Pause & Reflect: the user's reflection count, their latest readiness labels
and their own recent message checks (to optionally link a reflection to one)."""
from __future__ import annotations

from sqlalchemy import select

from app.models.analysis import MessageAnalysis
from app.page_context import _activity as act

RECENT_CHECKS = 8


def _recent_checks(db, user) -> list[dict]:
    rows = db.execute(
        select(MessageAnalysis)
        .where(MessageAnalysis.user_id == user.id)
        .order_by(MessageAnalysis.created_at.desc())
        .limit(RECENT_CHECKS)
    ).scalars()
    return [
        {
            "id": str(a.id),
            "snippet": act.snippet(a.text_for_display, 60) or "Message check",
            "when": act.time_ago(a.created_at),
        }
        for a in rows
    ]


def build(db, user) -> dict:
    latest = act.completed_reflections(db, user, limit=1)
    session = latest[0] if latest else None
    c = act.counts(db, user)
    return {
        "reflect": {
            "completed": c["reflections"],
            "pauses": c["pauses"],
            "latest": session,
            "latest_date": (
                act.aware(session.completed_at).astimezone().strftime("%d %b %Y")
                if session
                else ""
            ),
            "cards": act.dimension_cards(session),
            "checks": _recent_checks(db, user),
        }
    }
