"""Shared, user-scoped activity helpers for the Dashboard, My Journey,
Pause & Reflect and Decision Readiness pages.

Every query here filters on ``user_id == user.id``. Nothing is invented: when a
user has no rows the helpers return zeros, ``None`` or empty lists and the
templates show an honest empty state.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select

from app.models.analysis import MessageAnalysis
from app.models.enums import AnalysisStatus, ReflectionLabel
from app.models.learning import LearningProgress
from app.models.reflection import JournalEntry, ReflectionSession

# The five descriptive reflection dimensions stored on ReflectionSession.
DIMENSIONS: list[tuple[str, str]] = [
    ("reason_clarity", "Reason Clarity"),
    ("evidence_quality", "Evidence Quality"),
    ("time_pressure", "Time Pressure"),
    ("external_influence", "External Influence"),
    ("understanding", "Understanding"),
]

# Tailwind chip classes per reflection label (kept within the Stitch palette).
LABEL_CHIP = {
    ReflectionLabel.GOOD.value: "bg-tertiary-fixed text-on-tertiary-fixed",
    ReflectionLabel.NEEDS_REVIEW.value: "bg-secondary-fixed text-on-secondary-fixed",
    ReflectionLabel.PRESENT.value: "bg-secondary-fixed-dim text-on-secondary-fixed-variant",
    ReflectionLabel.DEVELOPING.value: "bg-surface-container-high text-on-surface-variant",
}
NOT_SET_CHIP = "bg-surface-container text-on-surface-variant"

LABEL_ICON = {
    ReflectionLabel.GOOD.value: ("check_circle", "text-tertiary"),
    ReflectionLabel.NEEDS_REVIEW.value: ("help", "text-secondary"),
    ReflectionLabel.PRESENT.value: ("groups", "text-secondary"),
    ReflectionLabel.DEVELOPING.value: ("schedule", "text-outline"),
}

STATUS_TEXT = {
    AnalysisStatus.MULTIPLE_SIGNALS.value: "Multiple signals detected",
    AnalysisStatus.NEEDS_VERIFICATION.value: "Needs verification",
    AnalysisStatus.NO_OBVIOUS_SIGNALS.value: "No obvious warning signals detected",
}
WARNING_STATUSES = (
    AnalysisStatus.MULTIPLE_SIGNALS.value,
    AnalysisStatus.NEEDS_VERIFICATION.value,
)


def aware(dt: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; treat them as UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def local_date(dt: datetime | None) -> date | None:
    dt = aware(dt)
    return dt.astimezone().date() if dt else None


def time_ago(dt: datetime | None) -> str:
    dt = aware(dt)
    if dt is None:
        return ""
    now = datetime.now(timezone.utc)
    seconds = max(0, int((now - dt).total_seconds()))
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        minutes = seconds // 60
        return "1 minute ago" if minutes == 1 else f"{minutes} minutes ago"
    if seconds < 86400:
        hours = seconds // 3600
        return "1 hour ago" if hours == 1 else f"{hours} hours ago"
    days = seconds // 86400
    if days == 1:
        return "Yesterday"
    if days < 7:
        return f"{days} days ago"
    return dt.astimezone().strftime("%d %b %Y")


def snippet(text: str | None, limit: int = 90) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _count(db, stmt) -> int:
    return int(db.execute(stmt).scalar() or 0)


# ---------------------------------------------------------------------------
# Counts
# ---------------------------------------------------------------------------


def completed_reflections(db, user, limit: int | None = None) -> list[ReflectionSession]:
    stmt = (
        select(ReflectionSession)
        .where(
            ReflectionSession.user_id == user.id,
            ReflectionSession.completed_at.is_not(None),
        )
        .order_by(ReflectionSession.completed_at.desc())
    )
    if limit:
        stmt = stmt.limit(limit)
    return list(db.execute(stmt).scalars().all())


def counts(db, user) -> dict:
    reflections = _count(
        db,
        select(func.count())
        .select_from(ReflectionSession)
        .where(
            ReflectionSession.user_id == user.id,
            ReflectionSession.completed_at.is_not(None),
        ),
    )
    pauses = _count(
        db,
        select(func.count())
        .select_from(ReflectionSession)
        .where(
            ReflectionSession.user_id == user.id,
            ReflectionSession.pause_completed.is_(True),
        ),
    )
    avg_pause = db.execute(
        select(func.avg(ReflectionSession.pause_seconds)).where(
            ReflectionSession.user_id == user.id,
            ReflectionSession.pause_completed.is_(True),
        )
    ).scalar()
    analyses = _count(
        db,
        select(func.count())
        .select_from(MessageAnalysis)
        .where(MessageAnalysis.user_id == user.id),
    )
    flagged = _count(
        db,
        select(func.count())
        .select_from(MessageAnalysis)
        .where(
            MessageAnalysis.user_id == user.id,
            MessageAnalysis.status.in_(WARNING_STATUSES),
        ),
    )
    concepts = _count(
        db,
        select(func.count())
        .select_from(LearningProgress)
        .where(
            LearningProgress.user_id == user.id,
            LearningProgress.completed_at.is_not(None),
        ),
    )
    journals = _count(
        db,
        select(func.count())
        .select_from(JournalEntry)
        .where(JournalEntry.user_id == user.id),
    )
    reasoning_good = _count(
        db,
        select(func.count())
        .select_from(ReflectionSession)
        .where(
            ReflectionSession.user_id == user.id,
            ReflectionSession.completed_at.is_not(None),
            ReflectionSession.reason_clarity == ReflectionLabel.GOOD.value,
        ),
    )
    return {
        "reflections": reflections,
        "pauses": pauses,
        "avg_pause_minutes": round(float(avg_pause) / 60, 1) if avg_pause else None,
        "analyses": analyses,
        "flagged": flagged,
        "concepts": concepts,
        "journals": journals,
        "reasoning_good": reasoning_good,
    }


def resilience_score(sessions: list[ReflectionSession]) -> int | None:
    """Share of reflection dimensions rated "Good" across completed reflections.

    A plain, explainable ratio of the user's own answers - not a ranking and
    not a judgement. ``None`` until at least one dimension has been rated.
    """
    rated = good = 0
    for s in sessions:
        for key, _ in DIMENSIONS:
            value = getattr(s, key)
            if value:
                rated += 1
                good += value == ReflectionLabel.GOOD.value
    if not rated:
        return None
    return round(good * 100 / rated)


# ---------------------------------------------------------------------------
# Daily activity, streak and heatmap
# ---------------------------------------------------------------------------


def activity_by_day(db, user, since: date) -> dict[date, set[str]]:
    """Map each local date to the kinds of activity the user did that day."""
    since_dt = datetime.combine(since - timedelta(days=1), datetime.min.time(), timezone.utc)
    days: dict[date, set[str]] = {}

    def add(dt, kind):
        d = local_date(dt)
        if d is not None and d >= since:
            days.setdefault(d, set()).add(kind)

    for (dt,) in db.execute(
        select(MessageAnalysis.created_at).where(
            MessageAnalysis.user_id == user.id, MessageAnalysis.created_at >= since_dt
        )
    ):
        add(dt, "check")
    for (dt,) in db.execute(
        select(ReflectionSession.created_at).where(
            ReflectionSession.user_id == user.id, ReflectionSession.created_at >= since_dt
        )
    ):
        add(dt, "reflect")
    for (dt,) in db.execute(
        select(JournalEntry.created_at).where(
            JournalEntry.user_id == user.id, JournalEntry.created_at >= since_dt
        )
    ):
        add(dt, "reflect")
    for (dt,) in db.execute(
        select(LearningProgress.updated_at).where(
            LearningProgress.user_id == user.id, LearningProgress.updated_at >= since_dt
        )
    ):
        add(dt, "learn")
    return days


def streak(days: dict[date, set[str]], today: date | None = None) -> int:
    """Consecutive active days ending today (or yesterday, if today is still empty)."""
    today = today or date.today()
    cursor = today if today in days else today - timedelta(days=1)
    run = 0
    while cursor in days:
        run += 1
        cursor -= timedelta(days=1)
    return run


def heatmap(days: dict[date, set[str]], today: date | None = None, weeks: int = 4) -> list[dict]:
    """Calendar cells (Mon-Sun rows) for the last ``weeks`` weeks up to today."""
    today = today or date.today()
    start = today - timedelta(days=today.weekday()) - timedelta(weeks=weeks - 1)
    cells = []
    for offset in range(weeks * 7):
        d = start + timedelta(days=offset)
        kinds = days.get(d, set())
        if d > today:
            kind = "future"
        elif "check" in kinds:
            kind = "check"
        elif "reflect" in kinds:
            kind = "reflect"
        elif "learn" in kinds:
            kind = "learn"
        else:
            kind = "none"
        cells.append({"day": d.day, "date": d, "kind": kind, "today": d == today})
    return cells


def badges(c: dict) -> list[dict]:
    """Milestones earned from the user's own counts. Thresholds are shown as-is."""
    return [
        {
            "name": "First Reflection",
            "detail": "Completed your first Pause & Reflect",
            "icon": "psychology_alt",
            "earned": c["reflections"] >= 1,
            "style": "bg-gradient-to-tr from-primary to-secondary text-on-primary",
        },
        {
            "name": "Disciplined Mind",
            "detail": "Completed five tactical pauses",
            "icon": "self_improvement",
            "earned": c["pauses"] >= 5,
            "style": "bg-tertiary-fixed text-on-tertiary-fixed-variant",
        },
        {
            "name": "Shield Guardian",
            "detail": "Checked 5+ messages for warning signals",
            "icon": "verified_user",
            "earned": c["analyses"] >= 5,
            "style": "bg-secondary-fixed text-on-secondary-fixed-variant",
        },
        {
            "name": "Informed Citizen",
            "detail": "Completed your first learning topic",
            "icon": "menu_book",
            "earned": c["concepts"] >= 1,
            "style": "bg-surface-container-high text-primary",
        },
    ]


def dimension_patterns(sessions: list[ReflectionSession]) -> list[dict]:
    """Most frequent label per dimension across the user's completed reflections."""
    out = []
    for key, name in DIMENSIONS:
        values = [getattr(s, key) for s in sessions if getattr(s, key)]
        if not values:
            continue
        label, n = Counter(values).most_common(1)[0]
        out.append(
            {
                "name": name,
                "label": label,
                "count": n,
                "total": len(values),
                "chip": LABEL_CHIP.get(label, NOT_SET_CHIP),
                "icon": LABEL_ICON.get(label, ("insights", "text-outline")),
            }
        )
    return out


def dimension_cards(session: ReflectionSession | None) -> list[dict]:
    cards = []
    for key, name in DIMENSIONS:
        value = getattr(session, key) if session is not None else None
        cards.append(
            {
                "key": key,
                "name": name,
                "label": value,
                "chip": LABEL_CHIP.get(value, NOT_SET_CHIP) if value else NOT_SET_CHIP,
                "icon": LABEL_ICON.get(value, ("schedule", "text-outline")),
            }
        )
    return cards
