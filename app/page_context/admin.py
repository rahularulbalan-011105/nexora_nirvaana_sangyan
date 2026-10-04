"""Admin console: aggregate counts and system/audit events only.

Product rule: administrators never see private user content. Nothing here
reads journal text, memories, voice transcripts or analysis text - only row
counts, and audit/system events stripped of user identity and IP address.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.config import settings
from app.models.analysis import BatchJob, MessageAnalysis, SafetyRule
from app.models.enums import AnalysisStatus
from app.models.learning import LearningContent
from app.models.system import AuditLog, FeatureFlag, SystemEvent
from app.models.user import Session as UserSession
from app.models.user import User
from app.models.voice import VoiceMessage, VoiceSession
from app.services import i18n

# Human labels for audit actions. Unknown actions fall back to a tidy form.
ACTION_LABELS = {
    "auth.login": ("Sign-in", "Authentication", "login"),
    "auth.login.failed": ("Failed sign-in attempt", "Authentication", "gpp_maybe"),
    "auth.logout": ("Sign-out", "Authentication", "logout"),
    "auth.register": ("New account registered", "Registration", "person_add"),
    "auth.email_verified": ("Email address verified", "Registration", "mark_email_read"),
    "auth.verification_resent": ("Verification email resent", "Registration", "forward_to_inbox"),
    "auth.reset_requested": ("Password reset requested", "Authentication", "lock_reset"),
    "auth.password_reset": ("Password reset completed", "Authentication", "key"),
    "report.journey": ("Journey report generated", "Reports", "summarize"),
    "privacy.export": ("Personal data export", "Privacy", "download"),
}

CHART_DAYS = 7


def _count(db, stmt) -> int:
    return int(db.execute(stmt).scalar() or 0)


def _since(days: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _activity(db, limit: int = 8) -> list[dict]:
    rows: list[dict] = []
    audits = db.execute(
        select(AuditLog.action, AuditLog.resource_type, AuditLog.outcome, AuditLog.created_at)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    ).all()
    for a in audits:
        label, category, icon = ACTION_LABELS.get(
            a.action,
            (a.action.replace(".", " ").replace("_", " ").capitalize(), "Audit", "verified"),
        )
        rows.append(
            {
                "title": label,
                "category": category,
                "icon": icon,
                "detail": a.action + (f" • {a.resource_type}" if a.resource_type else ""),
                "at": _as_utc(a.created_at),
                "ok": (a.outcome or "success") == "success",
                "status": (a.outcome or "success").capitalize(),
            }
        )
    events = db.execute(
        select(
            SystemEvent.level,
            SystemEvent.component,
            SystemEvent.event,
            SystemEvent.created_at,
        )
        .order_by(SystemEvent.created_at.desc())
        .limit(limit)
    ).all()
    for e in events:
        level = (e.level or "info").lower()
        rows.append(
            {
                "title": e.event,
                "category": e.component,
                "icon": "error" if level in ("error", "critical") else "monitor_heart",
                "detail": f"{e.component} • {level}",
                "at": _as_utc(e.created_at),
                "ok": level not in ("error", "critical", "warning"),
                "status": level.capitalize(),
            }
        )
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    rows.sort(key=lambda r: r["at"] or epoch, reverse=True)
    return rows[:limit]


def _daily_analyses(db) -> dict:
    """Analysis counts per day for the last week. Counts only, never content."""
    today = datetime.now(timezone.utc).date()
    start = datetime.combine(
        today - timedelta(days=CHART_DAYS - 1), datetime.min.time(), tzinfo=timezone.utc
    )
    rows = db.execute(
        select(MessageAnalysis.created_at, MessageAnalysis.status).where(
            MessageAnalysis.created_at >= start
        )
    ).all()
    buckets = {today - timedelta(days=i): [0, 0] for i in range(CHART_DAYS)}
    for created_at, status in rows:
        created = _as_utc(created_at)
        if created is None:
            continue
        day = created.date()
        if day in buckets:
            buckets[day][0] += 1
            if status == AnalysisStatus.MULTIPLE_SIGNALS.value:
                buckets[day][1] += 1
    days = sorted(buckets)
    peak = max((buckets[d][0] for d in days), default=0)
    bars = []
    for i, d in enumerate(days):
        total, flagged = buckets[d]
        total_h = round(100 * total / peak) if peak else 0
        flagged_h = round(100 * flagged / peak) if peak else 0
        x = 30 + i * 100
        bars.append(
            {
                "label": d.strftime("%a %d %b"),
                "total": total,
                "flagged": flagged,
                "x": x,
                "total_h": total_h,
                "total_y": 120 - total_h,
                "flagged_h": flagged_h,
                "flagged_y": 120 - flagged_h,
            }
        )
    week_total = sum(b["total"] for b in bars)
    return {
        "bars": bars,
        "total": week_total,
        "flagged": sum(b["flagged"] for b in bars),
        "has_data": week_total > 0,
    }


# Providers that answer without a language model.
OFFLINE_PROVIDERS = {"local", "rules"}
PROVIDER_LABELS = {
    "ollama": "Ollama (local model)",
    "local": "Offline templates",
    "rules": "Rule engine (checks)",
    "cache": "Answer cache",
}


def _ai_usage(db) -> dict:
    """AI calls by provider: last 7 days and today. Metadata only.

    Reads provider, latency and guardrail outcome columns - never message,
    transcript or analysis text. Talk turns use the provider recorded on the
    assistant row (older rows: the session's last provider); message checks
    use ``MessageAnalysis.ai_provider``. Guardrail-only answers (credential
    blocks, advice refusals) never reach a model and are counted separately.
    """
    now = datetime.now(timezone.utc)
    week_start = _since(CHART_DAYS)
    day_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)

    calls: list[tuple[str, datetime | None, int | None]] = []
    guardrail_week = 0
    talk_rows = db.execute(
        select(
            VoiceMessage.created_at,
            VoiceMessage.latency_ms,
            VoiceMessage.guardrail_notes,
            VoiceSession.ai_provider,
        )
        .join(VoiceSession, VoiceSession.id == VoiceMessage.session_id)
        .where(VoiceMessage.role == "assistant", VoiceMessage.created_at >= week_start)
    ).all()
    for created_at, latency, notes, session_provider in talk_rows:
        notes = notes if isinstance(notes, dict) else {}
        provider = notes.get("provider") or session_provider or "unknown"
        if notes.get("cached"):
            provider = "cache"
        if provider == "guardrail":
            guardrail_week += 1
            continue
        calls.append((provider, _as_utc(created_at), latency))

    for created_at, provider, ms in db.execute(
        select(
            MessageAnalysis.created_at, MessageAnalysis.ai_provider, MessageAnalysis.processing_ms
        ).where(MessageAnalysis.created_at >= week_start)
    ).all():
        calls.append((provider or "rules", _as_utc(created_at), ms))

    by_name: dict[str, dict] = {}
    for provider, created, ms in calls:
        row = by_name.setdefault(
            provider,
            {"name": provider, "label": PROVIDER_LABELS.get(provider, provider.title()),
             "week": 0, "today": 0, "_ms": [], "offline": provider in OFFLINE_PROVIDERS},
        )
        row["week"] += 1
        if created and created >= day_start:
            row["today"] += 1
        if ms is not None:
            row["_ms"].append(ms)

    week_total = len(calls)
    providers = []
    for row in sorted(by_name.values(), key=lambda r: r["week"], reverse=True):
        samples = row.pop("_ms")
        row["avg_ms"] = round(sum(samples) / len(samples)) if samples else None
        row["share_pct"] = round(100 * row["week"] / week_total) if week_total else 0
        providers.append(row)

    all_ms = [ms for _, _, ms in calls if ms is not None]
    offline = sum(r["week"] for r in providers if r["offline"])

    from app.services import cache  # local import: keeps page context light

    stats = cache.stats()
    hits, misses = stats.get("talk:hit", 0), stats.get("talk:miss", 0)
    return {
        "providers": providers,
        "week_total": week_total,
        "today_total": sum(r["today"] for r in providers),
        "offline_pct": round(100 * offline / week_total) if week_total else 0,
        "avg_ms": round(sum(all_ms) / len(all_ms)) if all_ms else None,
        "guardrail_week": guardrail_week,
        "cache_backend": cache.backend(),
        "cache_hits": hits,
        "cache_misses": misses,
        "cache_hit_pct": round(100 * hits / (hits + misses)) if hits + misses else None,
        "has_data": week_total > 0 or guardrail_week > 0,
    }


def build(db, user) -> dict:
    now = datetime.now(timezone.utc)
    start_of_day = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)

    users_total = _count(db, select(func.count()).select_from(User))
    users_new_30d = _count(
        db, select(func.count()).select_from(User).where(User.created_at >= _since(30))
    )
    users_verified = _count(
        db,
        select(func.count()).select_from(User).where(User.email_verified_at.is_not(None)),
    )
    active_24h = _count(
        db,
        select(func.count()).select_from(User).where(User.last_login_at >= _since(1)),
    )
    active_sessions = _count(
        db,
        select(func.count())
        .select_from(UserSession)
        .where(UserSession.revoked_at.is_(None), UserSession.expires_at > now),
    )
    analyses_today = _count(
        db,
        select(func.count())
        .select_from(MessageAnalysis)
        .where(MessageAnalysis.created_at >= start_of_day),
    )
    analyses_total = _count(db, select(func.count()).select_from(MessageAnalysis))
    batch_jobs = _count(db, select(func.count()).select_from(BatchJob))
    rules_enabled = _count(
        db, select(func.count()).select_from(SafetyRule).where(SafetyRule.enabled.is_(True))
    )
    rules_total = _count(db, select(func.count()).select_from(SafetyRule))
    flags_enabled = _count(
        db,
        select(func.count()).select_from(FeatureFlag).where(FeatureFlag.enabled.is_(True)),
    )
    flags_total = _count(db, select(func.count()).select_from(FeatureFlag))
    lessons_published = _count(
        db,
        select(func.count())
        .select_from(LearningContent)
        .where(LearningContent.published.is_(True)),
    )
    system_errors_24h = _count(
        db,
        select(func.count())
        .select_from(SystemEvent)
        .where(SystemEvent.level.in_(("error", "critical")), SystemEvent.created_at >= _since(1)),
    )

    languages = i18n.language_options()

    return {
        "admin": {
            "db_backend": "SQLite (development fallback)" if settings.is_sqlite else "PostgreSQL",
            "users_total": users_total,
            "users_new_30d": users_new_30d,
            "users_verified": users_verified,
            "active_24h": active_24h,
            "active_sessions": active_sessions,
            "analyses_today": analyses_today,
            "analyses_total": analyses_total,
            "batch_jobs": batch_jobs,
            "rules_enabled": rules_enabled,
            "rules_total": rules_total,
            "flags_enabled": flags_enabled,
            "flags_total": flags_total,
            "lessons_published": lessons_published,
            "system_errors_24h": system_errors_24h,
            "languages": languages,
            "language_count": len(languages),
            "activity": _activity(db),
            "chart": _daily_analyses(db),
            "ai_usage": _ai_usage(db),
        }
    }
