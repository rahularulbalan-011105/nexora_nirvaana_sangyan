"""Settings, Privacy Center and data-rights endpoints."""
from __future__ import annotations

import re

from sqlalchemy import func, select

from tests.conftest import csrf_of


def _hdr(client) -> dict:
    return {"X-CSRF-Token": csrf_of(client)}


def _user(db, email):
    from app.models.user import User

    db.expire_all()
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def _count(db, model, *where) -> int:
    db.expire_all()
    return int(db.execute(select(func.count()).select_from(model).where(*where)).scalar() or 0)


def test_settings_and_privacy_pages_render(auth_client):
    client = auth_client("pages@test.local")
    for path in ("/settings", "/privacy", "/help", "/offline", "/family"):
        response = client.get(path)
        assert response.status_code == 200, path
    html = client.get("/settings").text
    assert 'data-pref="voice_enabled"' in html
    assert 'data-privacy="memory_enabled"' in html
    assert "This device" in html
    help_html = client.get("/help").text
    for link in ("tel:1930", "https://cybercrime.gov.in/", "https://scores.sebi.gov.in/",
                 "https://cms.rbi.org.in/"):
        assert link in help_html


def test_preferences_persist(auth_client, db):
    client = auth_client("prefs@test.local")
    response = client.post(
        "/api/account/preferences",
        json={"voice_enabled": False, "large_text": True, "high_contrast": True,
              "data_saver": True, "offline_cache_enabled": False,
              "notifications_enabled": False, "simple_language": True, "speech_rate": 85},
        headers=_hdr(client),
    )
    assert response.status_code == 200, response.text
    prefs = _user(db, "prefs@test.local").preferences
    assert (prefs.voice_enabled, prefs.large_text, prefs.high_contrast) == (False, True, True)
    assert (prefs.data_saver, prefs.offline_cache_enabled) == (True, False)
    assert (prefs.notifications_enabled, prefs.simple_language) == (False, True)
    assert prefs.speech_rate == 85
    html = client.get("/settings").text
    assert 'data-pref="voice_enabled" type="checkbox">' in html  # unchecked now
    assert re.search(r'aria-pressed="true"[^>]*data-pref-choice="large_text" data-value="true"', html)
    assert re.search(r'aria-pressed="true"[^>]*data-pref-choice="high_contrast" data-value="true"', html)


def test_preferences_reject_unknown_and_bad_values(auth_client):
    client = auth_client("prefs-bad@test.local")
    bad = [{"is_admin": True}, {"language": "xx"}, {"large_text": "yes"}, {"speech_rate": "fast"}]
    for body in bad:
        response = client.post("/api/account/preferences", json=body, headers=_hdr(client))
        assert response.status_code == 400, body


def test_speech_rate_is_clamped(auth_client, db):
    client = auth_client("rate@test.local")
    client.post("/api/account/preferences", json={"speech_rate": 500}, headers=_hdr(client))
    assert _user(db, "rate@test.local").preferences.speech_rate == 130


def test_privacy_switches_persist(auth_client, db):
    client = auth_client("privacy@test.local")
    body = {"memory_enabled": True, "store_analysis_history": False,
            "store_voice_transcripts": True, "store_uploaded_files": True,
            "allow_family_access": True}
    response = client.post("/api/account/privacy", json=body, headers=_hdr(client))
    assert response.status_code == 200
    priv = _user(db, "privacy@test.local").privacy
    for key, value in body.items():
        assert getattr(priv, key) is value
    assert client.post("/api/account/privacy", json={"analytics_opt_in": True},
                       headers=_hdr(client)).status_code == 400


def test_account_routes_need_csrf(auth_client):
    client = auth_client("csrf-acct@test.local")
    assert client.post("/api/account/preferences", json={"large_text": True}).status_code == 403
    assert client.post("/api/account/delete", json={"confirm_text": "DELETE"}).status_code == 403


def test_memory_write_respects_the_switch(db, make_user):
    from app.models.reflection import Memory
    from app.services import account

    user = make_user(email="mem-guard@test.local")
    assert user.privacy.memory_enabled is False
    assert account.remember(db, user, "I prefer Tamil explanations") is None
    user.privacy.memory_enabled = True
    db.flush()
    assert account.remember(db, user, "My OTP is 482913") is None  # credentials never stored
    row = account.remember(db, user, "I prefer Tamil explanations")
    assert row is not None
    db.commit()
    assert _count(db, Memory, Memory.user_id == user.id) == 1


def test_manage_memory_delete_one_and_all(auth_client, db):
    from app.models.reflection import Memory

    client = auth_client("mem@test.local")
    user = _user(db, "mem@test.local")
    rows = [Memory(user_id=user.id, content=f"note {i}") for i in range(3)]
    db.add_all(rows)
    db.commit()
    assert "note 1" in client.get("/settings").text

    response = client.post(f"/api/account/memories/{rows[0].id}/delete", headers=_hdr(client))
    assert response.status_code == 200
    assert _count(db, Memory, Memory.user_id == user.id) == 2

    # Delete-all needs the explicit confirm flag.
    assert client.post("/api/account/memories/delete-all", json={},
                       headers=_hdr(client)).status_code == 400
    response = client.post("/api/account/memories/delete-all", json={"confirm": True},
                           headers=_hdr(client))
    assert response.json()["deleted"] == 2
    assert _count(db, Memory, Memory.user_id == user.id) == 0


def test_cannot_delete_someone_elses_memory(auth_client, make_user, db):
    from app.models.reflection import Memory

    other = make_user(email="mem-other@test.local")
    row = Memory(user_id=other.id, content="private")
    db.add(row)
    db.commit()
    client = auth_client("mem-attacker@test.local")
    response = client.post(f"/api/account/memories/{row.id}/delete", headers=_hdr(client))
    assert response.status_code == 404
    assert _count(db, Memory, Memory.id == row.id) == 1


def test_delete_analysis_voice_and_journal_history(auth_client, db):
    from app.models.analysis import AnalysisSignal, MessageAnalysis
    from app.models.reflection import JournalEntry
    from app.models.voice import VoiceMessage, VoiceSession

    client = auth_client("hist@test.local")
    user = _user(db, "hist@test.local")
    analysis = MessageAnalysis(user_id=user.id)
    db.add(analysis)
    db.flush()
    db.add(AnalysisSignal(analysis_id=analysis.id, signal_type="urgency"))
    voice = VoiceSession(user_id=user.id)
    db.add(voice)
    db.flush()
    db.add(VoiceMessage(session_id=voice.id, role="user", content="hello"))
    db.add(JournalEntry(user_id=user.id, title="t", body="b"))
    db.commit()
    analysis_id, voice_id = analysis.id, voice.id

    for kind in ("analysis", "voice", "journal"):
        no = client.post(f"/api/account/history/{kind}/delete", json={}, headers=_hdr(client))
        assert no.status_code == 400
        ok = client.post(f"/api/account/history/{kind}/delete", json={"confirm": True},
                         headers=_hdr(client))
        assert ok.status_code == 200 and ok.json()["deleted"] >= 1, kind

    assert _count(db, MessageAnalysis, MessageAnalysis.user_id == user.id) == 0
    assert _count(db, AnalysisSignal, AnalysisSignal.analysis_id == analysis_id) == 0
    assert _count(db, VoiceSession, VoiceSession.user_id == user.id) == 0
    assert _count(db, VoiceMessage, VoiceMessage.session_id == voice_id) == 0
    assert _count(db, JournalEntry, JournalEntry.user_id == user.id) == 0


def test_offline_notes_become_journal_entries(auth_client, db):
    from app.models.reflection import JournalEntry

    client = auth_client("offline@test.local")
    response = client.post(
        "/api/account/offline-notes",
        json={"notes": [{"text": "Felt rushed by a WhatsApp tip"}, {"text": "  "},
                        {"text": "my otp is 123456"}]},
        headers=_hdr(client),
    )
    assert response.json() == {"ok": True, "saved": 2}
    user = _user(db, "offline@test.local")
    bodies = db.execute(
        select(JournalEntry.body).where(JournalEntry.user_id == user.id,
                                        JournalEntry.created_offline.is_(True))
    ).scalars().all()
    assert len(bodies) == 2
    assert not any("123456" in b for b in bodies)


def test_revoke_other_session_but_not_this_one(auth_client, db):
    from app.models.user import Session
    from app.services import account

    client = auth_client("sess@test.local")
    user = _user(db, "sess@test.local")
    # A second sign-in from another "device".
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, follow_redirects=False) as other:
        other.get("/login")
        other.post("/login", data={"email": "sess@test.local", "password": "Harbour9Lantern",
                                   "_csrf": other.cookies.get("nirvaan_csrf")})
        assert other.get("/settings").status_code == 200
        current = account.current_session_id(db, client.cookies.get("nirvaan_session"))
        mine = client.post(f"/api/account/sessions/{current}/revoke", headers=_hdr(client))
        assert mine.status_code == 400
        db.expire_all()
        others = [s for s in db.execute(select(Session).where(
            Session.user_id == user.id, Session.revoked_at.is_(None))).scalars()
            if s.id != current]
        assert others
        ok = client.post(f"/api/account/sessions/{others[0].id}/revoke", headers=_hdr(client))
        assert ok.status_code == 200
        assert other.get("/settings").status_code in (302, 303, 307, 401)
    assert client.get("/settings").status_code == 200


def test_delete_account_requires_typed_confirmation_and_erases(auth_client, db):
    from app.models.reflection import JournalEntry, Memory
    from app.models.user import Session, User, UserPreferences

    client = auth_client("goodbye@test.local")
    user = _user(db, "goodbye@test.local")
    uid = user.id
    db.add(Memory(user_id=uid, content="x"))
    db.add(JournalEntry(user_id=uid, title="t", body="b"))
    db.commit()

    wrong = client.post("/api/account/delete", json={"confirm_text": "delete"},
                        headers=_hdr(client))
    assert wrong.status_code == 400
    assert _user(db, "goodbye@test.local") is not None

    response = client.post("/api/account/delete", json={"confirm_text": "DELETE"},
                           headers=_hdr(client))
    assert response.status_code == 200 and response.json()["redirect"] == "/"
    assert _user(db, "goodbye@test.local") is None
    for model in (Memory, JournalEntry, Session, UserPreferences):
        assert _count(db, model, model.user_id == uid) == 0, model.__name__
    assert _count(db, User, User.id == uid) == 0
    assert client.get("/settings").status_code in (302, 303, 307, 401)
