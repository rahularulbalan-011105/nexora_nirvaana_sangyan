"""Account self-service: preference/privacy switches and the user's data rights.

Every function acts only on rows owned by the given user. Deletions are real
SQL deletes; child rows go with them through ON DELETE CASCADE (SQLite runs
with ``PRAGMA foreign_keys=ON``).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, func, select, update

from app.config import settings
from app.models.analysis import BatchJob, MessageAnalysis, UploadedFile
from app.models.reflection import JournalEntry, Memory
from app.models.user import Session, User, UserPreferences, UserPrivacySettings
from app.models.voice import VoiceSession
from app.security import tokens
from app.services import responsible_ai as rai

# Switches the Settings / Privacy pages may change. Anything else is refused.
PREF_BOOL_FIELDS = frozenset(
    {
        "voice_enabled",
        "large_text",
        "high_contrast",
        "simple_language",
        "data_saver",
        "offline_cache_enabled",
        "notifications_enabled",
    }
)
PRIVACY_BOOL_FIELDS = frozenset(
    {
        "memory_enabled",
        "store_analysis_history",
        "store_voice_transcripts",
        "store_uploaded_files",
        "allow_family_access",
    }
)
SPEECH_RATE_RANGE = (70, 130)

OFFLINE_NOTE_MAX_CHARS = 4000
OFFLINE_NOTES_MAX = 50


def preferences(db, user: User) -> UserPreferences:
    if user.preferences is None:
        user.preferences = UserPreferences(user_id=user.id)
        db.flush()
    return user.preferences


def privacy(db, user: User) -> UserPrivacySettings:
    if user.privacy is None:
        user.privacy = UserPrivacySettings(user_id=user.id)
        db.flush()
    return user.privacy


def preference_state(user: User) -> dict:
    p = user.preferences
    state = {f: bool(getattr(p, f)) for f in PREF_BOOL_FIELDS} if p else {}
    state["speech_rate"] = p.speech_rate if p else 100
    return state


def privacy_state(user: User) -> dict:
    p = user.privacy
    return {f: bool(getattr(p, f)) for f in PRIVACY_BOOL_FIELDS} if p else {}


def update_preferences(db, user: User, changes: dict) -> dict:
    """Apply whitelisted preference changes. Raises ValueError on bad input."""
    prefs = preferences(db, user)
    for key, value in changes.items():
        if key in PREF_BOOL_FIELDS:
            if not isinstance(value, bool):
                raise ValueError(f"{key} must be true or false")
            setattr(prefs, key, value)
        elif key == "speech_rate":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("speech_rate must be a number")
            low, high = SPEECH_RATE_RANGE
            prefs.speech_rate = int(round(min(high, max(low, value))))
        else:
            raise ValueError(f"{key} cannot be changed here")
    return preference_state(user)


def update_privacy(db, user: User, changes: dict) -> dict:
    priv = privacy(db, user)
    for key, value in changes.items():
        if key not in PRIVACY_BOOL_FIELDS:
            raise ValueError(f"{key} cannot be changed here")
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be true or false")
        setattr(priv, key, value)
    return privacy_state(user)


# ---------------------------------------------------------------------------
# Guards other features should call before storing personal data
# ---------------------------------------------------------------------------


def memory_allowed(user: User) -> bool:
    return bool(user.privacy and user.privacy.memory_enabled)


def remember(db, user: User, content: str, *, type: str = "context", source: str = "user"):
    """The only sanctioned way to create a Memory row.

    Returns the new row, or None when memory is off or the content holds a
    credential (OTP, PIN, password, card or account number).
    """
    if not memory_allowed(user):
        return None
    allowed, cleaned, _found = rai.safe_to_remember(content or "")
    cleaned = (cleaned or "").strip()
    if not allowed or not cleaned:
        return None
    row = Memory(user_id=user.id, content=cleaned, type=type, source=source)
    db.add(row)
    db.flush()
    return row


def may_store_analysis(user: User) -> bool:
    return bool(user.privacy is None or user.privacy.store_analysis_history)


def may_store_uploads(user: User) -> bool:
    return bool(user.privacy and user.privacy.store_uploaded_files)


def may_notify(user: User) -> bool:
    return bool(user.preferences is None or user.preferences.notifications_enabled)


# ---------------------------------------------------------------------------
# Memories
# ---------------------------------------------------------------------------


def list_memories(db, user: User) -> list[Memory]:
    return list(
        db.execute(
            select(Memory).where(Memory.user_id == user.id).order_by(Memory.created_at.desc())
        ).scalars()
    )


def delete_memory(db, user: User, memory_id: str) -> bool:
    try:
        key = uuid.UUID(str(memory_id))
    except ValueError:
        return False
    result = db.execute(delete(Memory).where(Memory.id == key, Memory.user_id == user.id))
    return bool(result.rowcount)


def delete_all_memories(db, user: User) -> int:
    return db.execute(delete(Memory).where(Memory.user_id == user.id)).rowcount or 0


# ---------------------------------------------------------------------------
# History erasure
# ---------------------------------------------------------------------------


def _unlink_upload(stored_path: str | None) -> None:
    """Remove an uploaded file from disk, but only inside the upload folder."""
    if not stored_path:
        return
    try:
        root = settings.upload_path.resolve()
        path = Path(stored_path)
        path = (path if path.is_absolute() else root / path).resolve()
        if root in path.parents and path.is_file():
            path.unlink()
    except OSError:
        pass


def delete_uploads(db, user: User) -> int:
    rows = db.execute(
        select(UploadedFile.stored_path).where(UploadedFile.user_id == user.id)
    ).scalars().all()
    for stored in rows:
        _unlink_upload(stored)
    return db.execute(delete(UploadedFile).where(UploadedFile.user_id == user.id)).rowcount or 0


def delete_analysis_history(db, user: User) -> dict[str, int]:
    """Message checks (with signals and sources), batch jobs and uploads."""
    batches = db.execute(delete(BatchJob).where(BatchJob.user_id == user.id)).rowcount or 0
    analyses = (
        db.execute(delete(MessageAnalysis).where(MessageAnalysis.user_id == user.id)).rowcount
        or 0
    )
    uploads = delete_uploads(db, user)
    return {"analyses": analyses, "batches": batches, "uploads": uploads}


def delete_voice_history(db, user: User) -> int:
    """Voice sessions and every transcript line in them."""
    return db.execute(delete(VoiceSession).where(VoiceSession.user_id == user.id)).rowcount or 0


def delete_journal(db, user: User) -> int:
    return db.execute(delete(JournalEntry).where(JournalEntry.user_id == user.id)).rowcount or 0


def history_counts(db, user: User) -> dict[str, int]:
    def n(model, *where):
        return int(db.execute(select(func.count()).select_from(model).where(*where)).scalar() or 0)

    return {
        "memories": n(Memory, Memory.user_id == user.id),
        "analyses": n(MessageAnalysis, MessageAnalysis.user_id == user.id),
        "batches": n(BatchJob, BatchJob.user_id == user.id),
        "uploads": n(UploadedFile, UploadedFile.user_id == user.id),
        "voice_sessions": n(VoiceSession, VoiceSession.user_id == user.id),
        "journals": n(JournalEntry, JournalEntry.user_id == user.id),
    }


# ---------------------------------------------------------------------------
# Offline notes
# ---------------------------------------------------------------------------


def save_offline_notes(db, user: User, notes: list[dict]) -> int:
    """Turn notes written offline (kept in the browser) into journal entries."""
    language = user.language
    saved = 0
    for note in notes[:OFFLINE_NOTES_MAX]:
        text = str((note or {}).get("text") or "").strip()[:OFFLINE_NOTE_MAX_CHARS]
        if not text:
            continue
        cleaned, _found = rai.redact_sensitive(text)
        db.add(
            JournalEntry(
                user_id=user.id,
                title="Offline note",
                body=cleaned,
                language=language,
                created_offline=True,
            )
        )
        saved += 1
    db.flush()
    return saved


# ---------------------------------------------------------------------------
# Sessions and the account itself
# ---------------------------------------------------------------------------


def current_session_id(db, raw_token: str | None) -> uuid.UUID | None:
    if not raw_token:
        return None
    return db.execute(
        select(Session.id).where(Session.token_hash == tokens.hash_token(raw_token))
    ).scalar_one_or_none()


def revoke_session_by_id(db, user: User, session_id: str) -> bool:
    try:
        key = uuid.UUID(str(session_id))
    except ValueError:
        return False
    result = db.execute(
        update(Session)
        .where(Session.id == key, Session.user_id == user.id, Session.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    return bool(result.rowcount)


def delete_account(db, user: User) -> None:
    """Erase the user and everything they own. Audit rows keep no link to them."""
    delete_uploads(db, user)
    db.execute(delete(User).where(User.id == user.id))
