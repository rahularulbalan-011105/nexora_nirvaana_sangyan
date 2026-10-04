"""Authentication, session, CSRF and RBAC tests."""
from __future__ import annotations

import pytest

from app.models.enums import PermissionScope, Role
from app.security import tokens
from app.security.passwords import hash_password, password_problems, verify_password
from tests.conftest import csrf_of


# ---------------------------------------------------------------------------
# Password handling
# ---------------------------------------------------------------------------


def test_password_hash_is_argon2id_and_salted():
    first = hash_password("Harbour9Lantern")
    second = hash_password("Harbour9Lantern")
    assert first.startswith("$argon2id$")
    assert first != second, "each hash must use a fresh salt"
    assert verify_password("Harbour9Lantern", first)
    assert not verify_password("WrongPassphrase99", first)


def test_verify_rejects_a_malformed_hash_without_raising():
    assert verify_password("anything", "not-a-hash") is False


@pytest.mark.parametrize(
    "password,reason",
    [
        ("short1", "too short"),
        ("password1!", "common"),
        ("abcdefghijklmnop", "needs a digit"),
        ("1234567890123", "needs a letter"),
    ],
)
def test_weak_passwords_are_rejected(password, reason):
    assert password_problems(password), f"should reject ({reason}): {password}"


def test_password_cannot_contain_name_or_email():
    assert password_problems("priya12345678", name="Priya Sharma")
    assert password_problems("priya12345678", email="priya@example.com")


def test_reasonable_password_is_accepted():
    assert password_problems("QuietLotus7Harbour", email="a@b.com", name="Zed") == []


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


def test_only_the_token_digest_is_comparable():
    raw = tokens.new_token()
    digest = tokens.hash_token(raw)
    assert raw != digest
    assert len(digest) == 64
    assert tokens.tokens_match(raw, digest)
    assert not tokens.tokens_match(tokens.new_token(), digest)


def test_expiry_handles_naive_datetimes():
    """Rows read back from SQLite are naive; they must be treated as UTC."""
    from datetime import datetime, timedelta, timezone

    past = datetime.now(timezone.utc) - timedelta(hours=1)
    assert tokens.is_expired(past.replace(tzinfo=None))
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    assert not tokens.is_expired(future.replace(tzinfo=None))
    assert tokens.is_expired(None)


# ---------------------------------------------------------------------------
# Registration and login
# ---------------------------------------------------------------------------


def test_registration_creates_conservative_defaults(db, make_user):
    user = make_user(email="defaults@test.local")
    assert user.privacy is not None
    # Memory off by default is a spec requirement.
    assert user.privacy.memory_enabled is False
    assert user.privacy.store_voice_transcripts is False
    assert user.privacy.allow_family_access is False
    assert user.privacy.analytics_opt_in is False
    assert user.preferences is not None
    assert user.has_role(Role.USER)


def test_registration_does_not_reveal_existing_accounts(db, make_user):
    from app.services import auth as auth_service

    make_user(email="taken@test.local")
    result = auth_service.register(
        db,
        full_name="Someone Else",
        email="taken@test.local",
        password="DifferentPass88",
    )
    assert not result.ok
    # Must not say "already registered".
    assert "already" not in result.error_text.lower()


def test_login_failure_message_is_generic(db, make_user):
    from app.services import auth as auth_service

    make_user(email="generic@test.local", password="Harbour9Lantern")

    wrong_password = auth_service.login(
        db, email="generic@test.local", password="WrongPassphrase99"
    )
    no_account = auth_service.login(
        db, email="nobody@test.local", password="WrongPassphrase99"
    )
    assert wrong_password.errors == no_account.errors


def test_repeated_failures_lock_the_account(db, make_user):
    from app.services import auth as auth_service

    make_user(email="lockme@test.local", password="Harbour9Lantern")
    for _ in range(auth_service.MAX_FAILED_LOGINS):
        auth_service.login(db, email="lockme@test.local", password="Nope12345678")

    result = auth_service.login(
        db, email="lockme@test.local", password="Harbour9Lantern"
    )
    assert not result.ok, "correct password must still be refused while locked"
    assert "wait" in result.error_text.lower()


def test_session_token_is_stored_only_as_a_digest(db, make_user):
    from sqlalchemy import select

    from app.models.user import Session
    from app.services import auth as auth_service

    make_user(email="session@test.local", password="Harbour9Lantern")
    result = auth_service.login(
        db, email="session@test.local", password="Harbour9Lantern"
    )
    db.commit()

    raw = result.session_token
    assert raw
    rows = list(db.execute(select(Session)).scalars())
    assert all(row.token_hash != raw for row in rows), "raw token must not be stored"
    assert auth_service.resolve_session(db, raw) is not None
    assert auth_service.resolve_session(db, "wrong-token") is None


def test_password_reset_revokes_every_session(db, make_user):
    from app.services import auth as auth_service

    make_user(email="reset@test.local", password="Harbour9Lantern")
    login = auth_service.login(
        db, email="reset@test.local", password="Harbour9Lantern"
    )
    db.commit()
    assert auth_service.resolve_session(db, login.session_token) is not None

    _user, token = auth_service.issue_password_reset(db, "reset@test.local")
    outcome = auth_service.reset_password(
        db, raw_token=token, new_password="BrandNewPhrase44"
    )
    db.commit()
    assert outcome.ok
    assert auth_service.resolve_session(db, login.session_token) is None


def test_reset_token_is_single_use(db, make_user):
    from app.services import auth as auth_service

    make_user(email="once@test.local", password="Harbour9Lantern")
    _user, token = auth_service.issue_password_reset(db, "once@test.local")

    assert auth_service.reset_password(
        db, raw_token=token, new_password="FirstNewPhrase44"
    ).ok
    db.commit()
    assert not auth_service.reset_password(
        db, raw_token=token, new_password="SecondNewPhrase44"
    ).ok


def test_reset_for_unknown_email_yields_nothing(db):
    from app.services import auth as auth_service

    user, token = auth_service.issue_password_reset(db, "ghost@test.local")
    assert user is None and token is None


# ---------------------------------------------------------------------------
# HTTP-level auth
# ---------------------------------------------------------------------------


def test_protected_page_redirects_anonymous_to_login(client):
    response = client.get("/dashboard")
    assert response.status_code == 303
    assert "/login" in response.headers["location"]
    assert "next=%2Fdashboard" in response.headers["location"]


def test_api_returns_401_rather_than_redirecting(client):
    response = client.get("/api/providers", headers={"Accept": "application/json"})
    assert response.status_code == 401


def test_session_cookie_is_httponly(auth_client):
    client = auth_client(email="cookie@test.local")
    header = "; ".join(
        value for key, value in client.headers.items() if key.lower() == "cookie"
    )
    # The cookie jar holds it, but it must have been set HttpOnly.
    response = client.get("/login")
    assert response.status_code in (200, 303)
    # Re-login to inspect the Set-Cookie header directly.
    client.get("/login")
    token = csrf_of(client)
    fresh = client.post(
        "/login",
        data={
            "email": "cookie@test.local",
            "password": "Harbour9Lantern",
            "_csrf": token,
        },
    )
    set_cookie = fresh.headers.get("set-cookie", "")
    assert "httponly" in set_cookie.lower()
    assert "samesite" in set_cookie.lower()


def test_post_without_csrf_token_is_refused(client):
    response = client.post("/api/language", data={"language": "hi"})
    assert response.status_code == 403


def test_post_with_mismatched_csrf_token_is_refused(auth_client):
    client = auth_client(email="csrf@test.local")
    response = client.post(
        "/api/language", data={"language": "hi", "_csrf": "not-the-real-token"}
    )
    assert response.status_code == 403


def test_logout_clears_the_session(auth_client):
    client = auth_client(email="bye@test.local")
    assert client.get("/dashboard").status_code == 200

    client.post("/logout", data={"_csrf": csrf_of(client)})
    assert client.get("/dashboard").status_code == 303


def test_open_redirect_is_not_possible(auth_client, client, make_user):
    make_user(email="redirect@test.local", password="Harbour9Lantern")
    client.get("/login")
    response = client.post(
        "/login",
        data={
            "email": "redirect@test.local",
            "password": "Harbour9Lantern",
            "_csrf": csrf_of(client),
            "next": "https://evil.example.com/steal",
        },
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------


def test_normal_user_cannot_reach_the_admin_console(auth_client):
    client = auth_client(email="plain@test.local")
    assert client.get("/admin").status_code == 403


def test_admin_can_reach_the_admin_console(auth_client):
    client = auth_client(email="boss@test.local", role=Role.ADMIN)
    assert client.get("/admin").status_code == 200


def test_admin_is_refused_private_resource_types():
    from app.security.rbac import Forbidden, assert_not_private_for_admin

    for resource in ("journal_entries", "memories", "voice_messages"):
        with pytest.raises(Forbidden):
            assert_not_private_for_admin(resource)
    # Operational tables remain reachable.
    assert_not_private_for_admin("feature_flags")


def test_owned_repo_scopes_reads_to_the_owner(db, make_user):
    from app.models.reflection import JournalEntry
    from app.security.rbac import OwnedRepo

    alice = make_user(email="alice@test.local")
    bob = make_user(email="bob@test.local")

    alice_repo = OwnedRepo(db, JournalEntry, alice)
    entry = alice_repo.add(title="Private note", body="Only mine")
    db.commit()

    assert alice_repo.get(entry.id) is not None
    # Bob holds the real id but must still see nothing.
    bob_repo = OwnedRepo(db, JournalEntry, bob)
    assert bob_repo.get(entry.id) is None
    assert bob_repo.count() == 0


def test_owned_repo_refuses_a_non_owned_model(db, make_user):
    from app.models.system import FeatureFlag
    from app.security.rbac import OwnedRepo

    user = make_user(email="guard@test.local")
    with pytest.raises(TypeError):
        OwnedRepo(db, FeatureFlag, user)


def test_family_access_is_denied_without_consent(db, make_user):
    from app.models.family import FamilyRelationship
    from app.security.rbac import family_scope_allows

    owner = make_user(email="owner@test.local")
    helper = make_user(email="helper@test.local", role=Role.FAMILY_ASSISTANT)

    # A relationship with no consent and not active grants nothing.
    db.add(
        FamilyRelationship(
            owner_user_id=owner.id, assistant_user_id=helper.id, active=False
        )
    )
    db.commit()

    assert not family_scope_allows(
        db, assistant=helper, owner_id=owner.id, scope=PermissionScope.SAFETY_ONLY
    )


def test_family_access_follows_the_granted_scope(db, make_user):
    from datetime import datetime, timezone

    from app.models.family import FamilyPermission, FamilyRelationship
    from app.security.rbac import family_scope_allows

    owner = make_user(email="owner2@test.local")
    helper = make_user(email="helper2@test.local", role=Role.FAMILY_ASSISTANT)

    relationship = FamilyRelationship(
        owner_user_id=owner.id,
        assistant_user_id=helper.id,
        active=True,
        consent_granted_at=datetime.now(timezone.utc),
    )
    db.add(relationship)
    db.flush()
    db.add(
        FamilyPermission(
            relationship_id=relationship.id,
            scope=PermissionScope.SAFETY_ONLY.value,
            granted=True,
        )
    )
    db.commit()

    assert family_scope_allows(
        db, assistant=helper, owner_id=owner.id, scope=PermissionScope.SAFETY_ONLY
    )
    # An unlisted scope stays denied.
    assert not family_scope_allows(
        db, assistant=helper, owner_id=owner.id, scope=PermissionScope.JOURNAL_SHARED
    )


def test_revoking_a_relationship_removes_all_access(db, make_user):
    from datetime import datetime, timezone

    from app.models.family import FamilyPermission, FamilyRelationship
    from app.security.rbac import family_scope_allows

    owner = make_user(email="owner3@test.local")
    helper = make_user(email="helper3@test.local", role=Role.FAMILY_ASSISTANT)

    relationship = FamilyRelationship(
        owner_user_id=owner.id,
        assistant_user_id=helper.id,
        active=True,
        consent_granted_at=datetime.now(timezone.utc),
    )
    db.add(relationship)
    db.flush()
    db.add(
        FamilyPermission(
            relationship_id=relationship.id,
            scope=PermissionScope.SAFETY_ONLY.value,
            granted=True,
        )
    )
    db.commit()
    assert family_scope_allows(
        db, assistant=helper, owner_id=owner.id, scope=PermissionScope.SAFETY_ONLY
    )

    relationship.revoked_at = datetime.now(timezone.utc)
    relationship.active = False
    db.commit()

    assert not family_scope_allows(
        db, assistant=helper, owner_id=owner.id, scope=PermissionScope.SAFETY_ONLY
    )


# ---------------------------------------------------------------------------
# Audit log hygiene
# ---------------------------------------------------------------------------


def test_audit_detail_never_records_secrets(db):
    from app.services.audit import record

    entry = record(
        db,
        action="test.action",
        detail={"password": "hunter2", "otp_code": "123456", "page": "dashboard"},
    )
    db.commit()
    assert entry.detail["password"] == "[redacted]"
    assert entry.detail["otp_code"] == "[redacted]"
    assert entry.detail["page"] == "dashboard"
