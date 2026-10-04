"""JSON API: health, language switching, provider status.

Feature endpoints (analysis, voice, reflection, RAG) are added alongside their
features. This module holds the cross-cutting ones the shell already needs.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from app.config import settings
from app.db import engine
from app.deps import CurrentUser, DbDep, RequireAdmin, RequireUser, ThrottleApi, verify_csrf
from app.services import i18n
from app.services.ai import registry

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
def health(db: DbDep):
    """Liveness and dependency check for monitoring."""
    checks: dict[str, object] = {}

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {
            "healthy": True,
            "dialect": engine.dialect.name,
            # Flag the dev fallback loudly so it is never mistaken for Postgres.
            "note": "SQLite dev fallback" if settings.is_sqlite else "PostgreSQL",
        }
    except Exception as exc:  # noqa: BLE001
        checks["database"] = {"healthy": False, "error": str(exc)}

    providers = registry.health_report()
    checks["ai_providers"] = providers
    # The deterministic provider is always available, so AI is never fully down.
    checks["ai_available"] = any(p["healthy"] for p in providers)

    # Optional: memory fallbacks are healthy, so these never degrade status.
    from app.services import jobs, redis_client

    checks["redis"] = redis_client.status()
    checks["queue"] = jobs.status()

    overall = bool(checks["database"].get("healthy")) and bool(checks["ai_available"])
    return JSONResponse(
        {
            "status": "ok" if overall else "degraded",
            "app": settings.app_name,
            "environment": settings.app_env,
            "checks": checks,
        },
        status_code=200 if overall else 503,
    )


@router.get("/languages")
def languages():
    return {"languages": i18n.language_options(), "default": i18n.DEFAULT_LANGUAGE}


@router.post("/language", dependencies=[Depends(verify_csrf), ThrottleApi])
def set_language(
    request: Request,
    db: DbDep,
    user: CurrentUser,
    language: Annotated[str, Form()],
    next: Annotated[str, Form()] = "/dashboard",
):
    """Switch language. Persists to preferences when signed in, cookie otherwise."""
    code = i18n.normalise(language)

    if user is not None and user.preferences is not None:
        user.preferences.language = code
        db.commit()

    target = next if next.startswith("/") and not next.startswith("//") else "/dashboard"
    response = RedirectResponse(target, status_code=303)
    response.set_cookie(
        "nirvaan_lang",
        code,
        max_age=60 * 60 * 24 * 365,
        httponly=False,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/profile/gender", dependencies=[Depends(verify_csrf), ThrottleApi])
def set_gender(
    db: DbDep,
    user: RequireUser,
    gender: Annotated[str, Form()] = "",
):
    """Optional, self-described; only used to pick the companion avatar."""
    from app.services.auth import GENDERS

    user.gender = gender if gender in GENDERS else None
    db.commit()
    return RedirectResponse("/settings#profile", status_code=303)


@router.post("/notifications/{notification_id}/open", dependencies=[Depends(verify_csrf), ThrottleApi])
def notification_open(notification_id: str, db: DbDep, user: RequireUser):
    """The person opened a notification: mark it read, then go where it points."""
    import uuid
    from datetime import datetime, timezone

    from app.models.system import Notification

    try:
        key = uuid.UUID(notification_id)
    except ValueError:
        return RedirectResponse("/dashboard", status_code=303)
    note = db.execute(
        select(Notification).where(Notification.id == key, Notification.user_id == user.id)
    ).scalar_one_or_none()
    if note is None:
        return RedirectResponse("/dashboard", status_code=303)
    if note.read_at is None:
        note.read_at = datetime.now(timezone.utc)
        db.commit()
    link = note.link or "/dashboard"
    target = link if link.startswith("/") and not link.startswith("//") else "/dashboard"
    return RedirectResponse(target, status_code=303)


@router.post("/notifications/read-all", dependencies=[Depends(verify_csrf), ThrottleApi])
def notifications_read_all(
    db: DbDep,
    user: RequireUser,
    next: Annotated[str, Form()] = "/dashboard",
):
    """Mark every notification for the signed-in user as read."""
    from datetime import datetime, timezone

    from sqlalchemy import update

    from app.models.system import Notification

    db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(timezone.utc))
    )
    db.commit()
    target = next if next.startswith("/") and not next.startswith("//") else "/dashboard"
    return RedirectResponse(target, status_code=303)


class TalkRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    language: str = "en"
    session_id: str | None = None


@router.post("/talk", dependencies=[Depends(verify_csrf), ThrottleApi])
def talk(body: TalkRequest, db: DbDep, user: RequireUser):
    """One Talk to NIRVAAN turn: screened question in, screened answer out."""
    from app.services import talk as talk_service

    if not body.text.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Please say or type a question.")
    turn = talk_service.respond(db, user, body.text, body.language, body.session_id)
    db.commit()
    return turn.as_dict()


class TalkEndRequest(BaseModel):
    session_id: str


@router.post("/talk/end", dependencies=[Depends(verify_csrf), ThrottleApi])
def talk_end(body: TalkEndRequest, db: DbDep, user: RequireUser):
    """Close a voice session so the next question starts a new one."""
    import uuid
    from datetime import datetime, timezone

    from app.models.voice import VoiceSession

    try:
        key = uuid.UUID(body.session_id)
    except ValueError:
        return {"ended": False}
    session = db.execute(
        select(VoiceSession).where(VoiceSession.id == key, VoiceSession.user_id == user.id)
    ).scalar_one_or_none()
    if session is not None and session.ended_at is None:
        session.ended_at = datetime.now(timezone.utc)
        db.commit()
    return {"ended": session is not None}


@router.get("/providers", dependencies=[ThrottleApi])
def providers(user: RequireAdmin):
    """Provider status detail. Admin-only: it exposes model and host config."""
    return {"order": registry.order, "providers": registry.health_report()}
