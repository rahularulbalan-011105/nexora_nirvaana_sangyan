"""Pause & Reflect: label rules, the completion endpoint and the page."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.models.reflection import JournalEntry, ReflectionAnswer, ReflectionSession
from app.routers.feature_reflect import ReflectionIn, assess
from tests.conftest import csrf_of

BASE = {
    "reason": "researched",
    "reason_text": "Saving for my daughter's college fees in 2030",
    "evidence": ["registration", "documents"],
    "change_mind": "",
    "understanding": "yes",
    "deadline": "none",
    "commitment": "gt5",
    "essentials": "yes",
    "emotions": ["calm"],
    "counterfactual": "yes",
    "note": "",
    "save_journal": False,
    "elapsed_seconds": 95,
}


def _in(**over) -> ReflectionIn:
    return ReflectionIn(**{**BASE, **over})


# ---------------------------------------------------------------------------
# Deterministic label rules
# ---------------------------------------------------------------------------


def test_clear_reason_with_evidence_is_all_good():
    labels = assess(_in()).labels
    assert labels == {
        "reason_clarity": "Good",
        "evidence_quality": "Good",
        "time_pressure": "Good",
        "external_influence": "Good",
        "understanding": "Good",
    }


def test_social_pressure_and_urgency_are_present():
    r = assess(_in(reason="social", deadline="today", counterfactual="no",
                   evidence=["only_message"], understanding="no"))
    assert r.labels["reason_clarity"] == "Needs Review"
    assert r.labels["external_influence"] == "Present"
    assert r.labels["time_pressure"] == "Present"
    assert r.labels["evidence_quality"] == "Needs Review"
    assert r.labels["understanding"] == "Needs Review"
    assert r.signals["unverified"] and r.signals["external_influence"]


@pytest.mark.parametrize(
    "over,key,label",
    [
        ({"reason_text": ""}, "reason_clarity", "Developing"),
        ({"reason": "unsure"}, "reason_clarity", "Developing"),
        ({"reason": "fomo"}, "time_pressure", "Present"),
        ({"emotions": ["pressured"]}, "time_pressure", "Present"),
        ({"evidence": ["documents"]}, "evidence_quality", "Developing"),
        ({"understanding": "partly"}, "understanding", "Developing"),
        ({"reason": "recommended", "counterfactual": "unsure"}, "external_influence", "Present"),
        ({"reason": "recommended", "counterfactual": "yes"}, "external_influence", "Good"),
    ],
)
def test_individual_rules(over, key, label):
    assert assess(_in(**over)).labels[key] == label


def test_labels_never_contain_advice():
    allowed = {"Good", "Needs Review", "Present", "Developing"}
    for reason in ("researched", "recommended", "social", "fomo", "recover_loss", "unsure"):
        assert set(assess(_in(reason=reason)).labels.values()) <= allowed


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


def _post(client, body, csrf=True):
    headers = {"X-CSRF-Token": csrf_of(client)} if csrf else {}
    return client.post("/api/reflect/complete", json=body, headers=headers)


def test_requires_login(client):
    assert _post(client, BASE).status_code in (401, 403)


def test_requires_csrf(auth_client):
    client = auth_client(email="reflect-csrf@test.local")
    assert _post(client, BASE, csrf=False).status_code == 403


def test_missing_required_answer_is_rejected(auth_client):
    client = auth_client(email="reflect-invalid@test.local")
    body = {**BASE, "emotions": []}
    assert _post(client, body).status_code == 422
    body = {k: v for k, v in BASE.items() if k != "reason"}
    assert _post(client, body).status_code == 422


def test_completion_saves_session_answers_and_journal(auth_client, db):
    client = auth_client(email="reflect-ok@test.local")
    page = client.get("/reflect")
    assert page.status_code == 200
    assert "05:00" not in page.text
    assert "Reflections completed:" in page.text

    body = {**BASE, "reason": "social", "counterfactual": "no", "save_journal": True,
            "note": "Will ask my son first."}
    res = _post(client, body)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["ok"] and data["completed"] == 1 and data["journal_id"]
    assert {c["key"]: c["label"] for c in data["cards"]}["external_influence"] == "Present"
    assert all(c["reason"] for c in data["cards"])

    db.expire_all()
    session = db.get(ReflectionSession, uuid.UUID(data["id"]))
    assert session.completed_at is not None and session.pause_completed
    assert session.pause_seconds == 95
    assert session.reason_clarity == "Needs Review"
    assert session.summary == "Will ask my son first."
    keys = {a.question_key for a in session.answers}
    assert {"reason", "reason_text", "evidence", "understanding", "deadline",
            "commitment", "essentials", "emotions", "counterfactual", "note"} <= keys
    journal = db.get(JournalEntry, uuid.UUID(data["journal_id"]))
    assert journal.reflection_session_id == session.id
    assert journal.shared_with_family is False

    # Counts used by Dashboard / My Journey pick it up.
    from app.models.user import User
    from app.page_context import _activity as act

    user = db.get(User, session.user_id)
    assert act.counts(db, user)["reflections"] == 1
    page = client.get("/reflect")
    assert "Last Reflection" in page.text


def test_elapsed_time_is_clamped_and_no_journal_by_default(auth_client, db):
    client = auth_client(email="reflect-clamp@test.local")
    res = _post(client, {**BASE, "elapsed_seconds": 10**9})
    data = res.json()
    assert data["pause_seconds"] == 6 * 3600 and data["journal_id"] is None
    db.expire_all()
    n = db.execute(
        select(func.count()).select_from(ReflectionAnswer)
        .where(ReflectionAnswer.session_id == uuid.UUID(data["id"]))
    ).scalar()
    assert n >= 8


def test_cannot_link_someone_elses_analysis(auth_client, make_user, db):
    from app.models.analysis import MessageAnalysis

    other = make_user(email="reflect-other@test.local")
    foreign = MessageAnalysis(user_id=other.id, raw_text="Join our group for 30% returns")
    db.add(foreign)
    db.commit()

    client = auth_client(email="reflect-linker@test.local")
    res = _post(client, {**BASE, "analysis_id": str(foreign.id)})
    assert res.status_code == 404
    res = _post(client, {**BASE, "analysis_id": "not-a-uuid"})
    assert res.status_code == 404
