"""Decision Readiness: the scorecard from the user's latest completed reflection.

The five pillars are the descriptive labels stored on ReflectionSession; the
sixth card summarises the linked message check, if the reflection has one.
Nothing is shown as a verdict, and nothing is invented when no data exists.
"""
from __future__ import annotations

from sqlalchemy import select

from app.models.analysis import MessageAnalysis
from app.models.enums import ReflectionLabel
from app.page_context import _activity as act

# Static, educational explanation of what each pillar looks at.
PILLARS = {
    "reason_clarity": (
        "Clear Personal Objective",
        "Do you know, in your own words, why you are considering this decision?",
    ),
    "evidence_quality": (
        "Verifiable Evidence",
        "Is the claim backed by registered, verifiable information rather than screenshots or promises?",
    ),
    "time_pressure": (
        "Freedom From Rush",
        "Are deadlines, countdowns or “last few seats” language pushing you to act quickly?",
    ),
    "external_influence": (
        "Your Own Decision",
        "Is the push coming from groups, tips or people around you rather than your own goals?",
    ),
    "understanding": (
        "Product Understanding",
        "Could you explain how this product works and what you could lose?",
    ),
}


def build(db, user) -> dict:
    latest = act.completed_reflections(db, user, limit=1)
    session = latest[0] if latest else None

    analysis = None
    if session is not None and session.analysis_id is not None:
        analysis = db.execute(
            select(MessageAnalysis).where(
                MessageAnalysis.id == session.analysis_id,
                MessageAnalysis.user_id == user.id,
            )
        ).scalar_one_or_none()

    cards = []
    for i, card in enumerate(act.dimension_cards(session), start=1):
        headline, question = PILLARS[card["key"]]
        card.update({"number": i, "headline": headline, "question": question})
        cards.append(card)

    good = sum(1 for c in cards if c["label"] == ReflectionLabel.GOOD.value)
    rated = sum(1 for c in cards if c["label"])

    check = None
    if analysis is not None:
        flagged = analysis.status in act.WARNING_STATUSES
        check = {
            "status": act.STATUS_TEXT.get(analysis.status, "Checked"),
            "flagged": flagged,
            "signals": len(analysis.signals or []),
            "quote": act.snippet(analysis.text_for_display, 120),
            "when": act.time_ago(analysis.created_at),
        }

    return {
        "readiness": {
            "session": session,
            "date": (
                act.aware(session.completed_at).astimezone().strftime("%d %b %Y")
                if session
                else ""
            ),
            "summary": act.snippet(session.summary, 160) if session else "",
            "cards": cards,
            "good": good,
            "rated": rated,
            "check": check,
        }
    }
