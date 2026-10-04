"""Pause & Reflect routes.

``POST /api/reflect/complete`` stores one finished reflection: a
ReflectionSession with the five descriptive labels plus one ReflectionAnswer
row per question. The labels come from fixed, explainable rules in
``assess()`` - no model call, no prediction, and never buy/sell advice.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.deps import DbDep, RequireUser, ThrottleApi, verify_csrf
from app.models.analysis import MessageAnalysis
from app.models.enums import ReflectionLabel
from app.models.reflection import JournalEntry, ReflectionAnswer, ReflectionSession
from app.page_context import _activity as act

router = APIRouter(tags=["reflect"])

GOOD = ReflectionLabel.GOOD.value
REVIEW = ReflectionLabel.NEEDS_REVIEW.value
PRESENT = ReflectionLabel.PRESENT.value
DEVELOPING = ReflectionLabel.DEVELOPING.value

# Question keys, the English question text stored with each answer, and the
# English text of every option (stored so a past answer stays readable).
REASONS = {
    "researched": "I independently researched it",
    "recommended": "Someone recommended it",
    "social": "Everyone seems to be doing it",
    "fomo": "I don’t want to miss out (FOMO)",
    "recover_loss": "I want to recover a previous loss",
    "unsure": "I’m unsure",
}
EVIDENCE = {
    "registration": "Checked SEBI / RBI registration myself",
    "documents": "Read the official documents and charges",
    "independent": "Compared with an independent source",
    "only_message": "I only have the message or what I was told",
}
UNDERSTANDING = {
    "yes": "Yes, clearly",
    "partly": "Partly",
    "no": "Not really",
}
DEADLINE = {
    "today": "Today — I was told it ends soon",
    "week": "Within this week",
    "none": "No fixed deadline — I can take my time",
}
COMMITMENT = {
    "lt1": "Less than a year",
    "1to5": "1 to 5 years",
    "gt5": "More than 5 years",
    "unknown": "I don’t know yet",
}
ESSENTIALS = {
    "yes": "Yes, essentials stay covered",
    "unsure": "I’m not sure",
    "no": "No, it would affect essentials",
}
EMOTIONS = {
    "calm": "Calm",
    "hopeful": "Hopeful",
    "excited": "Excited",
    "anxious": "Anxious",
    "pressured": "Rushed or pressured",
    "fomo": "Afraid of missing out",
}
COUNTERFACTUAL = {
    "yes": "Yes, absolutely",
    "no": "No, probably not",
    "unsure": "Not sure",
}

QUESTIONS = {
    "reason": "Why are you considering this decision?",
    "reason_text": "In your own words, what is the reason?",
    "evidence": "What have you verified yourself?",
    "change_mind": "What verifiable information or disclosure would change your mind?",
    "understanding": "Could you explain how this works, including its fees and risks, to a family member?",
    "deadline": "When do you feel you need to decide?",
    "commitment": "How long would this money be committed?",
    "essentials": "If this money were locked or lost, would your essentials still be covered?",
    "emotions": "How are you feeling about this decision right now?",
    "counterfactual": "If nobody else had recommended this or mentioned it on social feeds, would you still make the same decision?",
    "note": "Anything you want to remember about this reflection?",
}

# A written reason counts as "clear" from this many words up.
CLEAR_REASON_WORDS = 4
MAX_PAUSE_SECONDS = 6 * 60 * 60


class ReflectionIn(BaseModel):
    reason: Literal["researched", "recommended", "social", "fomo", "recover_loss", "unsure"]
    reason_text: str = Field(default="", max_length=600)
    analysis_id: str | None = None
    evidence: list[Literal["registration", "documents", "independent", "only_message"]] = Field(
        min_length=1, max_length=4
    )
    change_mind: str = Field(default="", max_length=400)
    understanding: Literal["yes", "partly", "no"]
    deadline: Literal["today", "week", "none"]
    commitment: Literal["lt1", "1to5", "gt5", "unknown"]
    essentials: Literal["yes", "unsure", "no"]
    emotions: list[Literal["calm", "hopeful", "excited", "anxious", "pressured", "fomo"]] = Field(
        min_length=1, max_length=6
    )
    counterfactual: Literal["yes", "no", "unsure"]
    note: str = Field(default="", max_length=1500)
    save_journal: bool = False
    elapsed_seconds: int = 0

    @field_validator("reason_text", "change_mind", "note")
    @classmethod
    def _strip(cls, value: str) -> str:
        return " ".join(value.split()) if value else ""

    @field_validator("evidence", "emotions")
    @classmethod
    def _dedupe(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


# Plain-language reason behind each label, keyed so the page can show it
# in the reader's language.
WHY = {
    "rc_pressure": "The reason you picked comes from outside pressure or a past loss, not your own plan.",
    "rc_unsure": "You said you are unsure why you are considering this.",
    "rc_written": "You described your reason in your own words.",
    "rc_unwritten": "Writing the reason in your own words would make it clearer.",
    "eq_two": "You verified it in at least two independent ways.",
    "eq_one": "You verified it in one way so far.",
    "eq_none": "Nothing has been verified yet beyond the message or what you were told.",
    "tp_present": "You noted a same-day deadline or a feeling of being rushed.",
    "tp_none": "You did not report a deadline pushing you to decide today.",
    "ei_present": "Other people's enthusiasm seems to be part of this decision.",
    "ei_own": "You said you would make the same choice without others' recommendations.",
    "ei_none": "You did not report others pushing this decision.",
    "un_yes": "You said you could explain how it works, with its fees and risks.",
    "un_partly": "You said you partly understand how it works.",
    "un_no": "You said you could not yet explain how it works.",
}


@dataclass
class Assessment:
    labels: dict[str, str]
    reasons: dict[str, str]
    signals: dict[str, bool] = field(default_factory=dict)


def assess(a: ReflectionIn) -> Assessment:
    """Map answers to the five descriptive labels with a plain reason for each."""
    labels: dict[str, str] = {}
    why: dict[str, str] = {}
    emotions = set(a.emotions)

    # Reason clarity -------------------------------------------------------
    clear_text = len(a.reason_text.split()) >= CLEAR_REASON_WORDS
    if a.reason in ("social", "fomo", "recover_loss"):
        labels["reason_clarity"] = REVIEW
        why["reason_clarity"] = "rc_pressure"
    elif a.reason == "unsure":
        labels["reason_clarity"] = DEVELOPING
        why["reason_clarity"] = "rc_unsure"
    elif clear_text:
        labels["reason_clarity"] = GOOD
        why["reason_clarity"] = "rc_written"
    else:
        labels["reason_clarity"] = DEVELOPING
        why["reason_clarity"] = "rc_unwritten"

    # Evidence quality -----------------------------------------------------
    verified = [e for e in a.evidence if e != "only_message"]
    if len(verified) >= 2:
        labels["evidence_quality"] = GOOD
        why["evidence_quality"] = "eq_two"
    elif len(verified) == 1:
        labels["evidence_quality"] = DEVELOPING
        why["evidence_quality"] = "eq_one"
    else:
        labels["evidence_quality"] = REVIEW
        why["evidence_quality"] = "eq_none"

    # Time pressure --------------------------------------------------------
    rushed = a.deadline == "today" or a.reason == "fomo" or bool(emotions & {"pressured", "fomo"})
    labels["time_pressure"] = PRESENT if rushed else GOOD
    why["time_pressure"] = (
        "tp_present"
        if rushed
        else "tp_none"
    )

    # External influence ---------------------------------------------------
    influenced = (
        a.reason == "social"
        or a.counterfactual == "no"
        or (a.reason == "recommended" and a.counterfactual == "unsure")
    )
    labels["external_influence"] = PRESENT if influenced else GOOD
    why["external_influence"] = (
        "ei_present"
        if influenced
        else "ei_own"
        if a.counterfactual == "yes"
        else "ei_none"
    )

    # Understanding --------------------------------------------------------
    labels["understanding"] = {"yes": GOOD, "partly": DEVELOPING, "no": REVIEW}[a.understanding]
    why["understanding"] = {
        "yes": "un_yes",
        "partly": "un_partly",
        "no": "un_no",
    }[a.understanding]

    signals = {
        "time_pressure": labels["time_pressure"] == PRESENT,
        "external_influence": labels["external_influence"] == PRESENT,
        "fear_of_missing_out": a.reason == "fomo" or "fomo" in emotions,
        "loss_recovery": a.reason == "recover_loss",
        "unverified": not verified,
        "essentials_at_risk": a.essentials == "no",
    }
    return Assessment(labels=labels, reasons=why, signals=signals)


def _summary(a: ReflectionIn) -> str:
    if a.note:
        return a.note
    parts = [f"Reason: {REASONS[a.reason]}."]
    if a.reason_text:
        parts.append(f"In my words: {a.reason_text}.")
    parts.append("Verified: " + ", ".join(EVIDENCE[e] for e in a.evidence) + ".")
    parts.append(f"Deadline: {DEADLINE[a.deadline]}.")
    parts.append("Feeling: " + ", ".join(EMOTIONS[e] for e in a.emotions) + ".")
    return " ".join(parts)


def _answers(a: ReflectionIn, result: Assessment) -> list[ReflectionAnswer]:
    rows: list[ReflectionAnswer] = []

    def add(key: str, value: str | None, text: str | None, dimension: str | None = None):
        weight = 0.0
        if dimension:
            weight = 1.0 if result.labels[dimension] in (GOOD,) else 0.5 if result.labels[dimension] == DEVELOPING else 0.0
        rows.append(
            ReflectionAnswer(
                question_key=key,
                question_text=QUESTIONS[key],
                answer_value=value,
                answer_text=text,
                weight=weight,
            )
        )

    add("reason", a.reason, REASONS[a.reason], "reason_clarity")
    if a.reason_text:
        add("reason_text", None, a.reason_text, "reason_clarity")
    add("evidence", ",".join(a.evidence)[:64], "; ".join(EVIDENCE[e] for e in a.evidence), "evidence_quality")
    if a.change_mind:
        add("change_mind", None, a.change_mind)
    add("understanding", a.understanding, UNDERSTANDING[a.understanding], "understanding")
    add("deadline", a.deadline, DEADLINE[a.deadline], "time_pressure")
    add("commitment", a.commitment, COMMITMENT[a.commitment])
    add("essentials", a.essentials, ESSENTIALS[a.essentials])
    add("emotions", ",".join(a.emotions)[:64], "; ".join(EMOTIONS[e] for e in a.emotions), "time_pressure")
    add("counterfactual", a.counterfactual, COUNTERFACTUAL[a.counterfactual], "external_influence")
    if a.note:
        add("note", None, a.note)
    return rows


def _own_analysis(db, user, raw: str | None) -> uuid.UUID | None:
    if not raw:
        return None
    try:
        key = uuid.UUID(str(raw))
    except ValueError:
        return None
    found = db.execute(
        select(MessageAnalysis.id).where(
            MessageAnalysis.id == key, MessageAnalysis.user_id == user.id
        )
    ).scalar()
    return found


@router.post(
    "/api/reflect/complete",
    dependencies=[Depends(verify_csrf), ThrottleApi],
)
def complete_reflection(payload: ReflectionIn, db: DbDep, user: RequireUser):
    """Save a finished reflection and return its labels with their reasons."""
    if payload.analysis_id and _own_analysis(db, user, payload.analysis_id) is None:
        return JSONResponse(
            {"ok": False, "error": "That message check could not be found."}, status_code=404
        )

    result = assess(payload)
    now = datetime.now(timezone.utc)
    elapsed = max(0, min(int(payload.elapsed_seconds or 0), MAX_PAUSE_SECONDS))
    language = (user.preferences.language if user.preferences is not None else None) or "en"

    session = ReflectionSession(
        user_id=user.id,
        analysis_id=_own_analysis(db, user, payload.analysis_id),
        language=language,
        completed_at=now,
        summary=_summary(payload),
        signals_noticed=result.signals,
        pause_completed=True,
        pause_seconds=elapsed,
        **result.labels,
    )
    session.answers = _answers(payload, result)
    db.add(session)
    db.flush()

    journal_id = None
    if payload.save_journal:
        entry = JournalEntry(
            user_id=user.id,
            title=f"Reflection: {REASONS[payload.reason]}"[:200],
            body=session.summary,
            language=language,
            reflection_session_id=session.id,
            pause_seconds=elapsed,
            mood_note=", ".join(EMOTIONS[e] for e in payload.emotions)[:120],
            shared_with_family=False,  # journals stay private; sharing is a separate choice
        )
        db.add(entry)
        db.flush()
        journal_id = str(entry.id)
    db.commit()

    cards = act.dimension_cards(session)
    for card in cards:
        card["reason_key"] = result.reasons[card["key"]]
        card["reason"] = WHY[card["reason_key"]]
    counts = act.counts(db, user)
    return {
        "ok": True,
        "id": str(session.id),
        "journal_id": journal_id,
        "pause_seconds": elapsed,
        "cards": cards,
        "completed": counts["reflections"],
    }
