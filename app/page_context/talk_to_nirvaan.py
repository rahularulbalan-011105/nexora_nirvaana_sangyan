"""Talk to NIRVAAN: the signed-in user's own voice sessions."""
from __future__ import annotations

from sqlalchemy import func, select

from app.models.voice import VoiceSession


def build(db, user) -> dict:
    session_count = int(
        db.execute(
            select(func.count())
            .select_from(VoiceSession)
            .where(VoiceSession.user_id == user.id)
        ).scalar()
        or 0
    )
    latest = db.execute(
        select(VoiceSession)
        .where(VoiceSession.user_id == user.id)
        .order_by(VoiceSession.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    last_user_turn = None
    if latest is not None:
        # Only retained transcripts have text; others are stored with content NULL.
        turns = sorted(
            (m for m in latest.messages if m.role == "user" and m.content),
            key=lambda m: m.created_at,
        )
        last_user_turn = turns[-1] if turns else None

    return {
        "voice_session_count": session_count,
        "voice_latest_session": latest,
        "voice_last_user_turn": last_user_turn,
    }
