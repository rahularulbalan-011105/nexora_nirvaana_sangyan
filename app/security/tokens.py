"""Opaque single-use tokens for sessions, email verification and resets.

The raw token goes to the user (cookie or emailed link); only its SHA-256
digest is stored. A database leak therefore yields no usable session or
reset link.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

TOKEN_BYTES = 32  # 256 bits of entropy


def new_token() -> str:
    """URL-safe random token. Show this to the user exactly once."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    """Stable digest used as the database lookup key."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_match(token: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), stored_hash or "")


def expires_in(*, hours: int = 0, minutes: int = 0) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours, minutes=minutes)


def is_expired(moment: datetime | None) -> bool:
    if moment is None:
        return True
    # Rows read back from SQLite are naive; treat them as UTC.
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment <= datetime.now(timezone.utc)
