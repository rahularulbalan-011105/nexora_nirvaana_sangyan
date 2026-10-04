"""Test fixtures.

Each test module gets an isolated on-disk SQLite database, created before the
app is imported so ``app.config`` picks it up. Using a file rather than
``:memory:`` keeps the connection pool and the TestClient threadpool looking
at the same database.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Must be set before app.config is first imported.
_TMP = Path(tempfile.mkdtemp(prefix="nirvaan-test-"))
os.environ.update(
    {
        "USE_SQLITE_FALLBACK": "true",
        "SQLITE_PATH": str(_TMP / "test.db"),
        "SECRET_KEY": "test-secret-key-not-for-production-use",
        "APP_ENV": "development",
        "DEBUG": "false",
        "MAIL_BACKEND": "console",
        # Keep the limiter out of the way except where a test exercises it.
        "RATE_LIMIT_LOGIN_PER_MIN": "1000",
        "RATE_LIMIT_API_PER_MIN": "1000",
        # Force the deterministic provider so tests never depend on Ollama.
        "AI_PROVIDER_ORDER": "local",
        # In-process fallbacks; test_scalability injects fakeredis explicitly.
        "REDIS_URL": "",
    }
)


@pytest.fixture(scope="session", autouse=True)
def _schema():
    from app.db import Base, engine
    import app.models  # noqa: F401  registers tables

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="session")
def seeded(_schema):
    """Roles, flags, safety rules and content, seeded once per session."""
    from app.db import session_scope
    from scripts.seed import (
        seed_flags,
        seed_learning,
        seed_market,
        seed_roles,
        seed_safety_rules,
    )

    with session_scope() as db:
        seed_roles(db)
        seed_flags(db)
        seed_safety_rules(db)
        seed_learning(db)
        seed_market(db)
    return True


@pytest.fixture
def db(_schema):
    from app.db import SessionLocal

    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@pytest.fixture
def client(seeded):
    """Anonymous TestClient that does not follow redirects."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client


@pytest.fixture
def make_user(db):
    """Factory creating a verified account with a chosen role."""
    from datetime import datetime, timezone

    from app.models.enums import Role
    from app.services import auth as auth_service

    created: list[str] = []

    def _make(
        email: str = "user@test.local",
        password: str = "Harbour9Lantern",
        name: str = "Test Person",
        role: Role | str = Role.USER,
        language: str = "en",
        verified: bool = True,
    ):
        result = auth_service.register(
            db,
            full_name=name,
            email=email,
            password=password,
            language=language,
            role=role,
        )
        assert result.ok, f"could not create {email}: {result.errors}"
        if verified and result.user is not None:
            result.user.email_verified_at = datetime.now(timezone.utc)
        db.commit()
        created.append(email)
        return result.user

    return _make


@pytest.fixture
def auth_client(client, make_user):
    """Factory returning a TestClient already signed in as a given account."""

    def _login(email: str = "user@test.local", password: str = "Harbour9Lantern", **kwargs):
        make_user(email=email, password=password, **kwargs)
        client.get("/login")
        token = client.cookies.get("nirvaan_csrf")
        response = client.post(
            "/login", data={"email": email, "password": password, "_csrf": token}
        )
        assert response.status_code == 303, response.text[:400]
        return client

    return _login


def csrf_of(client) -> str:
    """Current CSRF token, refreshing it if the cookie is absent."""
    token = client.cookies.get("nirvaan_csrf")
    if not token:
        client.get("/login")
        token = client.cookies.get("nirvaan_csrf")
    return token or ""
