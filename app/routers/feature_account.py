"""account feature routes: settings switches, privacy switches and data rights.

All state-changing routes take JSON, require the CSRF header and act only on
the signed-in user's own rows. Destructive routes need an explicit
confirmation value in the body as well as the confirm step in the UI.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.deps import DbDep, RequireUser, ThrottleApi, verify_csrf
from app.services import account, audit

router = APIRouter(prefix="/api/account", tags=["account"])

Protected = [Depends(verify_csrf), ThrottleApi]
DELETE_WORD = "DELETE"


def _bad(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": message}, status_code=status)


def _confirmed(payload: dict | None) -> bool:
    return isinstance(payload, dict) and payload.get("confirm") is True


@router.post("/preferences", dependencies=Protected)
def set_preferences(db: DbDep, user: RequireUser, payload: dict[str, Any] = Body(...)):
    try:
        state = account.update_preferences(db, user, payload)
    except ValueError as exc:
        db.rollback()
        return _bad(str(exc))
    db.commit()
    return {"ok": True, "preferences": state}


@router.post("/privacy", dependencies=Protected)
def set_privacy(request: Request, db: DbDep, user: RequireUser, payload: dict[str, Any] = Body(...)):
    try:
        state = account.update_privacy(db, user, payload)
    except ValueError as exc:
        db.rollback()
        return _bad(str(exc))
    audit.record(
        db, action="privacy.update", user_id=user.id, request=request, detail=dict(payload)
    )
    db.commit()
    return {"ok": True, "privacy": state}


@router.get("/memories")
def memories(db: DbDep, user: RequireUser):
    return {
        "memory_enabled": account.memory_allowed(user),
        "memories": [
            {"id": str(m.id), "content": m.content, "type": m.type,
             "created_at": m.created_at.isoformat() if m.created_at else None}
            for m in account.list_memories(db, user)
        ],
    }


@router.post("/memories/{memory_id}/delete", dependencies=Protected)
def delete_memory(memory_id: str, db: DbDep, user: RequireUser):
    if not account.delete_memory(db, user, memory_id):
        return _bad("That memory could not be found.", 404)
    db.commit()
    return {"ok": True, "deleted": 1}


@router.post("/memories/delete-all", dependencies=Protected)
def delete_all_memories(
    request: Request, db: DbDep, user: RequireUser, payload: dict[str, Any] = Body(...)
):
    if not _confirmed(payload):
        return _bad("Please confirm before deleting.")
    deleted = account.delete_all_memories(db, user)
    audit.record(db, action="privacy.memories_deleted", user_id=user.id, request=request,
                 detail={"count": deleted})
    db.commit()
    return {"ok": True, "deleted": deleted}


@router.post("/history/{kind}/delete", dependencies=Protected)
def delete_history(
    kind: str, request: Request, db: DbDep, user: RequireUser,
    payload: dict[str, Any] = Body(...),
):
    if not _confirmed(payload):
        return _bad("Please confirm before deleting.")
    if kind == "analysis":
        counts = account.delete_analysis_history(db, user)
        deleted = counts["analyses"] + counts["batches"] + counts["uploads"]
    elif kind == "voice":
        counts = {"voice_sessions": account.delete_voice_history(db, user)}
        deleted = counts["voice_sessions"]
    elif kind == "journal":
        counts = {"journals": account.delete_journal(db, user)}
        deleted = counts["journals"]
    else:
        return _bad("Unknown history type.", 404)
    audit.record(db, action=f"privacy.{kind}_history_deleted", user_id=user.id,
                 request=request, detail=counts)
    db.commit()
    return {"ok": True, "deleted": deleted, "counts": counts}


@router.post("/offline-notes", dependencies=Protected)
def sync_offline_notes(db: DbDep, user: RequireUser, payload: dict[str, Any] = Body(...)):
    notes = payload.get("notes") if isinstance(payload, dict) else None
    if not isinstance(notes, list) or not notes:
        return _bad("No notes to save.")
    saved = account.save_offline_notes(db, user, [n for n in notes if isinstance(n, dict)])
    db.commit()
    return {"ok": True, "saved": saved}


@router.post("/sessions/{session_id}/revoke", dependencies=Protected)
def revoke_session(session_id: str, request: Request, db: DbDep, user: RequireUser):
    current = account.current_session_id(db, request.cookies.get(settings.session_cookie_name))
    if current is not None and str(current) == session_id:
        return _bad("This is the device you are using. Use Sign Out instead.")
    if not account.revoke_session_by_id(db, user, session_id):
        return _bad("That session could not be found or has already ended.", 404)
    audit.record(db, action="auth.session_revoked", user_id=user.id, request=request,
                 resource_type="session", resource_id=session_id)
    db.commit()
    return {"ok": True}


@router.post("/delete", dependencies=Protected)
def delete_account(request: Request, db: DbDep, user: RequireUser,
                   payload: dict[str, Any] = Body(...)):
    typed = str((payload or {}).get("confirm_text") or "").strip()
    if typed != DELETE_WORD:
        return _bad(f"Type {DELETE_WORD} to confirm.")
    user_id = user.id
    account.delete_account(db, user)
    # The audit row outlives the account but no longer points at it.
    audit.record(db, action="account.deleted", request=request,
                 resource_type="user", resource_id=str(user_id))
    db.commit()
    response = JSONResponse({"ok": True, "redirect": "/"})
    response.delete_cookie(settings.session_cookie_name, path="/")
    return response
