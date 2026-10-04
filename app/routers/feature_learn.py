"""Learn & Explore routes: lesson pages and per-user progress APIs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.deps import DbDep, RequireUser, ThrottleApi, verify_csrf
from app.services import learning_progress as lp
from app.templating import render, resolve_language

router = APIRouter(tags=["learn"])


@router.get("/learn/{slug}", response_class=HTMLResponse)
def learn_module(slug: str, request: Request, user: RequireUser, db: DbDep):
    """One lesson in Simple / Detailed / Example / Analogy modes."""
    language = resolve_language(request, user)
    ctx = lp.module_context(db, user, slug, language)
    if ctx is None:
        raise HTTPException(status_code=404, detail="This lesson does not exist.")
    return render(
        request,
        "pages/learn_module.html",
        user=user,
        db=db,
        active_nav="learn-and-explore",
        **ctx,
    )


def _lesson_or_404(db, slug: str):
    content = lp.get_lesson(db, slug)
    if content is None:
        raise HTTPException(status_code=404, detail="This lesson does not exist.")
    return content


def _payload(row) -> dict:
    data = lp.progress_dict(row)
    return {"ok": True, **data}


class ModesIn(BaseModel):
    modes_seen: int = Field(ge=1, le=4)


class BookmarkIn(BaseModel):
    bookmarked: bool


_post = dict(dependencies=[Depends(verify_csrf), ThrottleApi])


@router.post("/api/learn/{slug}/view", **_post)
def learn_view(slug: str, user: RequireUser, db: DbDep):
    return _payload(lp.record_view(db, user, _lesson_or_404(db, slug)))


@router.post("/api/learn/{slug}/progress", **_post)
def learn_progress(slug: str, body: ModesIn, user: RequireUser, db: DbDep):
    return _payload(lp.record_modes(db, user, _lesson_or_404(db, slug), body.modes_seen))


@router.post("/api/learn/{slug}/complete", **_post)
def learn_complete(slug: str, user: RequireUser, db: DbDep):
    return _payload(lp.mark_complete(db, user, _lesson_or_404(db, slug)))


@router.post("/api/learn/{slug}/bookmark", **_post)
def learn_bookmark(slug: str, body: BookmarkIn, user: RequireUser, db: DbDep):
    return _payload(lp.set_bookmark(db, user, _lesson_or_404(db, slug), body.bookmarked))
