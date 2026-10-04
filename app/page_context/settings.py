"""Profile & Settings: the signed-in user's own profile, preferences and sessions."""
from __future__ import annotations

from app.config import settings as app_settings
from app.page_context import _account_data as data
from app.services import account


def _speed_nuance(speed: float) -> str:
    # Mirrors the slider's client-side labels in settings.html.
    if speed < 0.85:
        return "Deep & Gentle"
    if speed <= 0.95:
        return "Calm & Measured"
    if speed <= 1.1:
        return "Neutral"
    return "Brisk Flow"


def build(db, user) -> dict:
    prefs = user.preferences
    rate = (prefs.speech_rate if prefs and prefs.speech_rate else 100) / 100
    rate = min(1.3, max(0.7, rate))
    counts = data.record_counts(db, user)
    return {
        "profile": {
            "name": user.full_name,
            "email": user.email,
            "initials": data.initials(user.full_name),
            "verified": user.email_verified_at is not None,
            "member_since": data.fmt_month(user.created_at),
            "last_login": data.time_ago(user.last_login_at),
            "language": prefs.language if prefs else "en",
            "language_name": data.LANGUAGE_NAMES.get(prefs.language if prefs else "en", "English"),
            "reflections_completed": counts["reflections_completed"],
        },
        "voice_speed": f"{rate:.2f}",
        "voice_speed_label": f"{rate:.2f}x • {_speed_nuance(rate)}",
        "sessions": data.active_sessions(db, user),
        # Called from the template with the request, so the row for this
        # browser can be labelled and kept out of "end session".
        "current_session_id": lambda request: str(
            account.current_session_id(
                db, request.cookies.get(app_settings.session_cookie_name)
            )
        ),
        "storage": data.storage_usage(db, user),
        "memories": [
            {"id": str(m.id), "content": m.content, "created": data.fmt_date(m.created_at)}
            for m in account.list_memories(db, user)
        ],
        "history_counts": account.history_counts(db, user),
        "speech_rate_pct": int(round(rate * 100)),
    }
