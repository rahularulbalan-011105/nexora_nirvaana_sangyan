"""Shared helpers for the account-facing pages (settings, privacy, family, offline).

Everything here reads rows owned by the given user only.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select

from app.models.analysis import MessageAnalysis, UploadedFile
from app.models.enums import InvitationStatus
from app.models.family import FamilyInvitation, FamilyRelationship
from app.models.learning import LearningProgress
from app.models.reflection import JournalEntry, ReflectionSession
from app.models.user import Session, User

LANGUAGE_NAMES = {"en": "English", "hi": "हिन्दी", "ta": "தமிழ்"}

SCOPE_LABELS = {
    "SAFETY_ONLY": "Safety alerts",
    "LEARNING_ONLY": "Learning progress",
    "JOURNAL_SHARED": "Shared journal",
}


def aware(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; treat them as UTC."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def fmt_date(value: datetime | None) -> str | None:
    value = aware(value)
    return value.strftime("%d %b %Y").lstrip("0") if value else None


def fmt_month(value: datetime | None) -> str | None:
    value = aware(value)
    return value.strftime("%b %Y") if value else None


def fmt_datetime(value: datetime | None) -> str | None:
    value = aware(value)
    if value is None:
        return None
    return value.strftime("%d %b %Y, %H:%M UTC").lstrip("0")


def time_ago(value: datetime | None, now: datetime | None = None) -> str | None:
    value = aware(value)
    if value is None:
        return None
    now = now or datetime.now(timezone.utc)
    seconds = max(0, int((now - value).total_seconds()))
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hr ago" if hours == 1 else f"{hours} hrs ago"
    days = hours // 24
    if days < 30:
        return "1 day ago" if days == 1 else f"{days} days ago"
    return fmt_date(value)


def human_bytes(size: int | None) -> str:
    size = int(size or 0)
    if size < 1024:
        return f"{size} B"
    for unit in ("KB", "MB", "GB"):
        size_f = size / 1024
        if size_f < 1024 or unit == "GB":
            return f"{size_f:.1f} {unit}"
        size = size_f
    return f"{size} B"  # pragma: no cover


def initials(name: str | None) -> str:
    parts = [p for p in (name or "").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def count(db, model, *where) -> int:
    return int(db.execute(select(func.count()).select_from(model).where(*where)).scalar() or 0)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


def describe_user_agent(ua: str | None) -> tuple[str, str]:
    """Return (readable label, material icon) for a User-Agent string."""
    ua = ua or ""
    low = ua.lower()
    if not ua:
        return "Unknown device", "devices"

    if "edg/" in low:
        browser = "Edge"
    elif "opr/" in low or "opera" in low:
        browser = "Opera"
    elif "firefox/" in low:
        browser = "Firefox"
    elif "chrome/" in low or "crios/" in low:
        browser = "Chrome"
    elif "safari/" in low:
        browser = "Safari"
    elif "python-httpx" in low or "python-requests" in low or "curl/" in low:
        browser = "Script client"
    elif "testclient" in low:
        browser = "Test client"
    else:
        browser = "Browser"

    if "android" in low:
        os_name, icon = "Android", "smartphone"
    elif "iphone" in low or "ipad" in low or "ios" in low:
        os_name, icon = "iOS", "smartphone"
    elif "windows" in low:
        os_name, icon = "Windows", "computer"
    elif "mac os" in low or "macintosh" in low:
        os_name, icon = "macOS", "laptop_mac"
    elif "cros" in low:
        os_name, icon = "ChromeOS", "laptop_chromebook"
    elif "linux" in low:
        os_name, icon = "Linux", "computer"
    else:
        os_name, icon = "", "devices"

    label = f"{browser} on {os_name}" if os_name else browser
    return label, icon


def active_sessions(db, user: User) -> list[dict]:
    now = datetime.now(timezone.utc)
    rows = db.execute(
        select(Session)
        .where(Session.user_id == user.id, Session.revoked_at.is_(None))
        .order_by(Session.created_at.desc())
    ).scalars()
    sessions = []
    for row in rows:
        expires = aware(row.expires_at)
        if expires is not None and expires <= now:
            continue
        label, icon = describe_user_agent(row.user_agent)
        sessions.append(
            {
                "id": str(row.id),
                "label": label,
                "icon": icon,
                "ip": row.ip_address,
                "signed_in": time_ago(row.created_at, now),
                "signed_in_at": fmt_datetime(row.created_at),
            }
        )
    return sessions


# ---------------------------------------------------------------------------
# Counts of the user's stored records
# ---------------------------------------------------------------------------


def record_counts(db, user: User) -> dict[str, int]:
    return {
        "journals": count(db, JournalEntry, JournalEntry.user_id == user.id),
        "analyses": count(db, MessageAnalysis, MessageAnalysis.user_id == user.id),
        "lessons_completed": count(
            db,
            LearningProgress,
            LearningProgress.user_id == user.id,
            LearningProgress.completed_at.is_not(None),
        ),
        "reflections_completed": count(
            db,
            ReflectionSession,
            ReflectionSession.user_id == user.id,
            ReflectionSession.completed_at.is_not(None),
        ),
    }


def storage_usage(db, user: User) -> dict:
    uploads = int(
        db.execute(
            select(func.coalesce(func.sum(UploadedFile.size_bytes), 0)).where(
                UploadedFile.user_id == user.id, UploadedFile.purged_at.is_(None)
            )
        ).scalar()
        or 0
    )
    journal_bytes = int(
        db.execute(
            select(
                func.coalesce(
                    func.sum(func.length(JournalEntry.body) + func.length(JournalEntry.title)), 0
                )
            ).where(JournalEntry.user_id == user.id)
        ).scalar()
        or 0
    )
    total = uploads + journal_bytes
    pct = (lambda part: round(part * 100 / total, 1) if total else 0)
    return {
        "total": human_bytes(total),
        "uploads": human_bytes(uploads),
        "reflections": human_bytes(journal_bytes),
        "uploads_pct": pct(uploads),
        "reflections_pct": pct(journal_bytes),
        "is_empty": total == 0,
    }


# ---------------------------------------------------------------------------
# Family
# ---------------------------------------------------------------------------


def family_links(db, user: User) -> list[dict]:
    """Every relationship where the user is either the owner or the assistant."""
    rows = db.execute(
        select(FamilyRelationship)
        .where(
            or_(
                FamilyRelationship.owner_user_id == user.id,
                FamilyRelationship.assistant_user_id == user.id,
            )
        )
        .order_by(FamilyRelationship.created_at.asc())
    ).scalars().all()

    other_ids = {
        r.assistant_user_id if r.owner_user_id == user.id else r.owner_user_id for r in rows
    }
    others: dict[uuid.UUID, User] = {}
    if other_ids:
        others = {
            u.id: u for u in db.execute(select(User).where(User.id.in_(other_ids))).scalars()
        }

    links = []
    for r in rows:
        i_am_owner = r.owner_user_id == user.id
        other = others.get(r.assistant_user_id if i_am_owner else r.owner_user_id)
        name = other.full_name if other else "Unknown member"
        lang = other.language if other else None
        if r.revoked_at is not None:
            status = "revoked"
        elif r.active:
            status = "active"
        else:
            status = "pending"
        links.append(
            {
                "name": name,
                "first_name": name.split(" ")[0] if name else "",
                "initials": initials(name),
                "email": other.email if other else None,
                "label": (r.relationship_label or "family").replace("_", " ").title(),
                "role": "assistant" if i_am_owner else "owner",
                "language": LANGUAGE_NAMES.get(lang or "", None),
                "status": status,
                "scopes": [SCOPE_LABELS.get(s, s) for s in sorted(r.granted_scopes)],
                "since": fmt_date(r.consent_granted_at or r.created_at),
            }
        )
    return links


def pending_invitations(db, user: User) -> list[dict]:
    rows = db.execute(
        select(FamilyInvitation)
        .where(
            FamilyInvitation.status == InvitationStatus.PENDING.value,
            or_(
                FamilyInvitation.inviter_user_id == user.id,
                func.lower(FamilyInvitation.invitee_email) == (user.email or "").lower(),
            ),
        )
        .order_by(FamilyInvitation.created_at.desc())
    ).scalars().all()
    now = datetime.now(timezone.utc)
    invites = []
    for inv in rows:
        expires = aware(inv.expires_at)
        if expires is not None and expires <= now:
            continue
        sent = inv.inviter_user_id == user.id
        inviter_name = None
        if not sent:
            inviter = db.get(User, inv.inviter_user_id)
            inviter_name = inviter.full_name if inviter else None
        invites.append(
            {
                "direction": "sent" if sent else "received",
                "email": inv.invitee_email,
                "inviter_name": inviter_name,
                "scopes": [SCOPE_LABELS.get(s, s) for s in inv.requested_scope_list],
                "sent": time_ago(inv.created_at, now),
                "expires": fmt_date(inv.expires_at),
            }
        )
    return invites
