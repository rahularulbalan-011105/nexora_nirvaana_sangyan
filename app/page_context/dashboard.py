"""Dashboard data: the signed-in user's own insights and recent activity.

The route already supplies ``metrics``; this adds the remaining figures and the
activity feed. Keys must not collide with the route's own keyword arguments.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from app.models.analysis import MessageAnalysis
from app.models.learning import LearningProgress
from app.models.reflection import JournalEntry
from app.page_context import _activity as act
from app.page_context.check_a_message import analysis_view


def _check_summary(analysis: MessageAnalysis) -> dict:
    """Pop-up content for a past message check: what was asked and what was found."""
    view = analysis_view(analysis)
    sections = [
        ("What we detected", analysis.what_we_detected),
        ("Why it matters", analysis.why_it_matters),
        ("What to verify", analysis.what_to_verify),
        ("What remains uncertain", analysis.what_is_uncertain),
    ]
    return {
        "text": view["text"],
        "status_label": view["meta"]["label"],
        "status_summary": view["meta"]["summary"],
        "tone": view["meta"]["tone"],
        "sections": [(title, body) for title, body in sections if body],
        "signals": [
            {
                "label": view["signal_label"][sig.id],
                "evidence": sig.evidence,
                "explanation": sig.explanation,
            }
            for sig in view["signals"][:5]
        ],
        "facts": [],
    }


def _recent(db, user, limit: int = 5) -> list[dict]:
    items: list[dict] = []

    for a in db.execute(
        select(MessageAnalysis)
        .where(MessageAnalysis.user_id == user.id)
        .order_by(MessageAnalysis.created_at.desc())
        .limit(limit)
    ).scalars():
        flagged = a.status in act.WARNING_STATUSES
        items.append(
            {
                "kind": "check",
                "when": act.aware(a.created_at),
                "title": "Checked a message",
                "quote": act.snippet(a.text_for_display, 80),
                "badge": act.STATUS_TEXT.get(a.status, "Checked"),
                "badge_class": (
                    "bg-error-container text-on-error-container"
                    if flagged
                    else "bg-tertiary-container/15 text-tertiary"
                ),
                "detail": " • ".join(
                    act.snippet(s.explanation or s.signal_type.replace("_", " ").title(), 60)
                    for s in (a.signals or [])[:3]
                ),
                "icon": "warning" if flagged else "verified_user",
                "icon_class": (
                    "bg-error-container text-on-error-container"
                    if flagged
                    else "bg-primary-fixed text-primary"
                ),
                "href": "/check",
                "action": "Check another",
                "summary": _check_summary(a),
            }
        )

    for s in act.completed_reflections(db, user, limit=limit):
        labelled = [
            f"{name}: {getattr(s, key)}" for key, name in act.DIMENSIONS if getattr(s, key)
        ]
        items.append(
            {
                "kind": "reflect",
                "when": act.aware(s.completed_at),
                "title": "Completed Pause & Reflect",
                "quote": act.snippet(s.summary, 80),
                "badge": "Pause completed" if s.pause_completed else "",
                "badge_class": "bg-tertiary-container/15 text-tertiary",
                "detail": " • ".join(labelled[:3]),
                "icon": "hourglass_top",
                "icon_class": "bg-secondary-fixed/60 text-secondary",
                "href": "/journey",
                "action": "View in My Journey",
                "summary": {
                    "text": s.summary or "",
                    "facts": [(name, getattr(s, key)) for key, name in act.DIMENSIONS if getattr(s, key)]
                    + [("Time paused", f"{round((s.pause_seconds or 0) / 60, 1)} min")],
                },
            }
        )

    for p in db.execute(
        select(LearningProgress)
        .where(
            LearningProgress.user_id == user.id,
            LearningProgress.completed_at.is_not(None),
        )
        .order_by(LearningProgress.completed_at.desc())
        .limit(limit)
    ).scalars():
        content = p.content
        items.append(
            {
                "kind": "learn",
                "when": act.aware(p.completed_at),
                "title": "Learned a concept",
                "quote": content.title if content else "",
                "badge": f"{content.reading_minutes} min read" if content else "",
                "badge_class": "bg-primary-fixed text-on-primary-fixed",
                "detail": act.snippet(content.summary if content else "", 110),
                "icon": "school",
                "icon_class": "bg-primary-fixed text-primary",
                "href": "/learn",
                "action": "Revisit topics",
                "summary": {
                    "text": (content.summary if content else "") or "",
                    "facts": [("Reading time", f"{content.reading_minutes} min")] if content else [],
                },
            }
        )

    for j in db.execute(
        select(JournalEntry)
        .where(JournalEntry.user_id == user.id)
        .order_by(JournalEntry.created_at.desc())
        .limit(limit)
    ).scalars():
        items.append(
            {
                "kind": "journal",
                "when": act.aware(j.created_at),
                "title": "Journal entry",
                "quote": act.snippet(j.title or j.body, 80),
                "badge": "Private" if not j.shared_with_family else "Shared with family",
                "badge_class": "bg-surface-container-high text-on-surface-variant",
                "detail": act.snippet(j.body, 110) if j.title else "",
                "icon": "edit_note",
                "icon_class": "bg-tertiary-fixed text-tertiary",
                "href": "/journey",
                "action": "Open My Journey",
                "summary": {"text": j.body or j.title or "", "facts": []},
            }
        )

    items = [i for i in items if i["when"] is not None]
    items.sort(key=lambda i: i["when"], reverse=True)
    for i in items:
        i["ago"] = act.time_ago(i["when"])
    return items[:limit]


def build(db, user) -> dict:
    c = act.counts(db, user)
    sessions = act.completed_reflections(db, user)
    days = act.activity_by_day(db, user, date.today() - timedelta(days=400))
    earned = [b for b in act.badges(c) if b["earned"]]
    return {
        "dash": {
            "streak": act.streak(days),
            "resilience_score": act.resilience_score(sessions),
            "reasoning_good": c["reasoning_good"],
            "signals_flagged": c["flagged"],
            "messages_checked": c["analyses"],
            "badges_earned": len(earned),
        },
        "recent_activity": _recent(db, user),
    }
