"""Registration, login, sessions, email verification and password reset."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.models.enums import Language, Role
from app.models.user import (
    EmailVerification,
    PasswordReset,
    RoleRow,
    Session,
    User,
    UserPreferences,
    UserPrivacySettings,
)
from app.security import tokens
from app.security.passwords import (
    hash_password,
    needs_rehash,
    password_problems,
    verify_password,
)

# Failed logins before the account is briefly locked.
MAX_FAILED_LOGINS = 8
LOCKOUT_MINUTES = 15
VERIFICATION_TTL_HOURS = 24
RESET_TTL_MINUTES = 60


@dataclass
class AuthResult:
    ok: bool
    user: User | None = None
    errors: list[str] = field(default_factory=list)
    # Raw session token, set only on a successful login.
    session_token: str | None = None

    @property
    def error_text(self) -> str:
        return " ".join(self.errors)


def normalise_email(email: str) -> str:
    return (email or "").strip().lower()


def get_user_by_email(db: DbSession, email: str) -> User | None:
    return db.execute(
        select(User).where(User.email == normalise_email(email))
    ).scalar_one_or_none()


def ensure_role(db: DbSession, name: Role | str) -> RoleRow:
    """Fetch a role row, creating it if the seed has not run."""
    key = str(name)
    row = db.execute(select(RoleRow).where(RoleRow.name == key)).scalar_one_or_none()
    if row is None:
        row = RoleRow(name=key, description=f"{key} role")
        db.add(row)
        db.flush()
    return row


def assign_role(db: DbSession, user: User, role: Role | str) -> None:
    from app.models.user import UserRole

    role_row = ensure_role(db, role)
    exists = db.execute(
        select(UserRole).where(
            UserRole.user_id == user.id, UserRole.role_id == role_row.id
        )
    ).scalar_one_or_none()
    if exists is None:
        db.add(UserRole(user_id=user.id, role_id=role_row.id))


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------


GENDERS = {"female", "male", "other"}


def register(
    db: DbSession,
    *,
    full_name: str,
    email: str,
    password: str,
    language: str = Language.EN.value,
    role: Role | str = Role.USER,
    gender: str | None = None,
) -> AuthResult:
    """Create an account.

    Only name, email, password and preferred language are collected - no
    financial information is requested at sign-up.
    """
    email = normalise_email(email)
    name = (full_name or "").strip()
    errors: list[str] = []

    if len(name) < 2:
        errors.append("Please enter your name.")
    if "@" not in email or "." not in email.split("@")[-1]:
        errors.append("Please enter a valid email address.")
    errors.extend(password_problems(password, email=email, name=name))

    if errors:
        return AuthResult(ok=False, errors=errors)

    if get_user_by_email(db, email) is not None:
        # Generic wording: do not confirm which addresses are registered.
        return AuthResult(
            ok=False,
            errors=["That email cannot be used to register. Try signing in instead."],
        )

    if language not in {lang.value for lang in Language}:
        language = Language.EN.value

    if gender not in GENDERS:
        gender = None

    user = User(
        email=email,
        full_name=name,
        gender=gender,
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(user)
    db.flush()

    # Conservative defaults: memory OFF, transcripts not stored.
    db.add(UserPreferences(user_id=user.id, language=language))
    db.add(UserPrivacySettings(user_id=user.id))
    assign_role(db, user, role)
    db.flush()

    return AuthResult(ok=True, user=user)


# --------------------------------------------------------------------------
# Login / sessions
# --------------------------------------------------------------------------


def _is_locked(user: User) -> bool:
    if user.locked_until is None:
        return False
    locked_until = user.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    return locked_until > datetime.now(timezone.utc)


def login(
    db: DbSession,
    *,
    email: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuthResult:
    generic = ["Email or password is incorrect."]
    user = get_user_by_email(db, email)

    if user is None:
        # Spend comparable time so a missing account is not detectable by timing.
        verify_password(password, hash_password("timing-equaliser"))
        return AuthResult(ok=False, errors=generic)

    if _is_locked(user):
        return AuthResult(
            ok=False,
            errors=[
                "Too many failed attempts. Please wait a few minutes and try again."
            ],
        )

    if not user.is_active:
        return AuthResult(ok=False, errors=["This account is not active."])

    if not verify_password(password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= MAX_FAILED_LOGINS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=LOCKOUT_MINUTES
            )
            user.failed_login_count = 0
        db.flush()
        return AuthResult(ok=False, errors=generic)

    # Upgrade the stored hash if Argon2 parameters have moved on.
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = datetime.now(timezone.utc)

    token = create_session(db, user, ip_address=ip_address, user_agent=user_agent)
    db.flush()
    return AuthResult(ok=True, user=user, session_token=token)


def create_session(
    db: DbSession,
    user: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> str:
    """Mint a session row and return the raw token for the cookie."""
    raw = tokens.new_token()
    db.add(
        Session(
            user_id=user.id,
            token_hash=tokens.hash_token(raw),
            expires_at=tokens.expires_in(hours=settings.session_ttl_hours),
            ip_address=(ip_address or "")[:64] or None,
            user_agent=(user_agent or "")[:255] or None,
        )
    )
    return raw


def resolve_session(db: DbSession, raw_token: str | None) -> User | None:
    """Return the signed-in user for a cookie token, or None."""
    if not raw_token:
        return None

    row = db.execute(
        select(Session).where(Session.token_hash == tokens.hash_token(raw_token))
    ).scalar_one_or_none()

    if row is None or row.revoked_at is not None or tokens.is_expired(row.expires_at):
        return None

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        return None
    return user


def revoke_session(db: DbSession, raw_token: str | None) -> bool:
    if not raw_token:
        return False
    row = db.execute(
        select(Session).where(Session.token_hash == tokens.hash_token(raw_token))
    ).scalar_one_or_none()
    if row is None:
        return False
    row.revoked_at = datetime.now(timezone.utc)
    return True


def revoke_all_sessions(db: DbSession, user: User, *, except_token: str | None = None) -> int:
    keep = tokens.hash_token(except_token) if except_token else None
    rows = db.execute(
        select(Session).where(Session.user_id == user.id, Session.revoked_at.is_(None))
    ).scalars()
    count = 0
    now = datetime.now(timezone.utc)
    for row in rows:
        if keep and row.token_hash == keep:
            continue
        row.revoked_at = now
        count += 1
    return count


# --------------------------------------------------------------------------
# Email verification
# --------------------------------------------------------------------------


def issue_email_verification(db: DbSession, user: User) -> str:
    raw = tokens.new_token()
    db.add(
        EmailVerification(
            user_id=user.id,
            token_hash=tokens.hash_token(raw),
            expires_at=tokens.expires_in(hours=VERIFICATION_TTL_HOURS),
        )
    )
    db.flush()
    return raw


def consume_email_verification(db: DbSession, raw_token: str) -> AuthResult:
    row = db.execute(
        select(EmailVerification).where(
            EmailVerification.token_hash == tokens.hash_token(raw_token)
        )
    ).scalar_one_or_none()

    if row is None or row.consumed_at is not None or tokens.is_expired(row.expires_at):
        return AuthResult(
            ok=False, errors=["That verification link is invalid or has expired."]
        )

    user = db.get(User, row.user_id)
    if user is None:
        return AuthResult(ok=False, errors=["That verification link is no longer valid."])

    now = datetime.now(timezone.utc)
    row.consumed_at = now
    if user.email_verified_at is None:
        user.email_verified_at = now
    db.flush()
    return AuthResult(ok=True, user=user)


# --------------------------------------------------------------------------
# Password reset
# --------------------------------------------------------------------------


def issue_password_reset(db: DbSession, email: str) -> tuple[User | None, str | None]:
    """Create a reset token.

    Returns ``(None, None)`` for unknown addresses; callers must still show the
    same confirmation message so the endpoint cannot enumerate accounts.
    """
    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        return None, None

    raw = tokens.new_token()
    db.add(
        PasswordReset(
            user_id=user.id,
            token_hash=tokens.hash_token(raw),
            expires_at=tokens.expires_in(minutes=RESET_TTL_MINUTES),
        )
    )
    db.flush()
    return user, raw


def reset_password(db: DbSession, *, raw_token: str, new_password: str) -> AuthResult:
    row = db.execute(
        select(PasswordReset).where(
            PasswordReset.token_hash == tokens.hash_token(raw_token)
        )
    ).scalar_one_or_none()

    if row is None or row.consumed_at is not None or tokens.is_expired(row.expires_at):
        return AuthResult(ok=False, errors=["That reset link is invalid or has expired."])

    user = db.get(User, row.user_id)
    if user is None:
        return AuthResult(ok=False, errors=["That reset link is no longer valid."])

    problems = password_problems(new_password, email=user.email, name=user.full_name)
    if problems:
        return AuthResult(ok=False, errors=problems)

    user.password_hash = hash_password(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    row.consumed_at = datetime.now(timezone.utc)
    # A reset invalidates every existing session.
    revoke_all_sessions(db, user)
    db.flush()
    return AuthResult(ok=True, user=user)


def change_password(
    db: DbSession, *, user: User, current_password: str, new_password: str
) -> AuthResult:
    if not verify_password(current_password, user.password_hash):
        return AuthResult(ok=False, errors=["Your current password is incorrect."])

    problems = password_problems(new_password, email=user.email, name=user.full_name)
    if problems:
        return AuthResult(ok=False, errors=problems)

    user.password_hash = hash_password(new_password)
    db.flush()
    return AuthResult(ok=True, user=user)


def purge_expired(db: DbSession) -> dict[str, int]:
    """Housekeeping for the background job: drop stale auth rows."""
    now = datetime.now(timezone.utc)
    counts: dict[str, int] = {}
    for label, model in (
        ("sessions", Session),
        ("email_verifications", EmailVerification),
        ("password_resets", PasswordReset),
    ):
        rows = list(db.execute(select(model).where(model.expires_at < now)).scalars())
        for row in rows:
            db.delete(row)
        counts[label] = len(rows)
    return counts


def user_id_of(value: uuid.UUID | str) -> uuid.UUID | None:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None
