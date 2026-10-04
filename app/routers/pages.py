"""Page routes.

Every authenticated page is served from its generated Stitch template. At this
foundation stage the routes establish routing, authorization, language and the
shared context; the per-feature data wiring is layered on from here.
"""
from __future__ import annotations

import importlib

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select

from app.config import settings
from app.deps import CurrentUser, DbDep, RequireAdmin, RequireUser
from app.models.learning import LearningProgress
from app.models.reflection import JournalEntry, ReflectionSession
from app.templating import render

router = APIRouter(tags=["pages"])


def _page_context(nav_key: str, db, user) -> dict:
    """Per-page data from ``app/page_context/<nav_key>.py`` if that module exists.

    Each module exposes ``build(db, user) -> dict``; the dict is merged into the
    template context. Pages without a module render with the shared context only.
    """
    name = f"app.page_context.{nav_key.replace('-', '_')}"
    try:
        module = importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if exc.name == name:
            return {}
        raise
    return module.build(db, user)


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
def landing(request: Request, user: CurrentUser, db: DbDep):
    if user is not None:
        return RedirectResponse("/dashboard", status_code=303)
    return render(
        request,
        "pages/landing.html",
        db=db,
        active_nav="landing",
        demo_video_url=settings.demo_video_url,
    )


@router.get("/demo", response_class=HTMLResponse)
def demo(request: Request, user: CurrentUser, db: DbDep):
    """Walkthrough video linked from the landing hero.

    The URL lives in ``DEMO_VIDEO_URL`` so it can be changed without a code
    change. With no URL configured the landing button is hidden, so this route
    is only reachable by typing it; say so plainly rather than redirecting
    nowhere.
    """
    if settings.demo_video_url:
        return RedirectResponse(settings.demo_video_url, status_code=303)
    return render(
        request,
        "pages/landing.html",
        db=db,
        user=user,
        active_nav="landing",
        demo_video_url="",
        notice="The walkthrough video is not available yet. Create an account to explore now.",
    )


# ---------------------------------------------------------------------------
# Authenticated pages
# ---------------------------------------------------------------------------


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, user: RequireUser, db: DbDep):
    """Resilience metrics come from the user's own rows only."""
    reflections_completed = int(
        db.execute(
            select(func.count())
            .select_from(ReflectionSession)
            .where(
                ReflectionSession.user_id == user.id,
                ReflectionSession.completed_at.is_not(None),
            )
        ).scalar()
        or 0
    )
    pause_moments = int(
        db.execute(
            select(func.count())
            .select_from(ReflectionSession)
            .where(
                ReflectionSession.user_id == user.id,
                ReflectionSession.pause_completed.is_(True),
            )
        ).scalar()
        or 0
    )
    concepts_learned = int(
        db.execute(
            select(func.count())
            .select_from(LearningProgress)
            .where(
                LearningProgress.user_id == user.id,
                LearningProgress.completed_at.is_not(None),
            )
        ).scalar()
        or 0
    )
    journal_count = int(
        db.execute(
            select(func.count())
            .select_from(JournalEntry)
            .where(JournalEntry.user_id == user.id)
        ).scalar()
        or 0
    )

    return render(
        request,
        "pages/dashboard.html",
        user=user,
        db=db,
        active_nav="dashboard",
        welcome=request.query_params.get("welcome") == "1",
        metrics={
            "reflections_completed": reflections_completed,
            "pause_moments": pause_moments,
            "concepts_learned": concepts_learned,
            "journal_entries": journal_count,
            # Streak needs the reflection history walker; wired with the
            # My Journey feature rather than guessed at here.
            "reflection_streak": None,
        },
        **_page_context("dashboard", db, user),
    )


def _simple_page(path: str, template: str, nav_key: str, title: str):
    """Register a page that currently needs no extra query work."""

    @router.get(path, response_class=HTMLResponse, name=f"page_{nav_key}")
    def _page(request: Request, user: RequireUser, db: DbDep):  # noqa: ANN202
        return render(
            request,
            template,
            user=user,
            db=db,
            active_nav=nav_key,
            **_page_context(nav_key, db, user),
        )

    _page.__name__ = f"page_{nav_key.replace('-', '_')}"
    _page.__doc__ = f"{title} page."
    return _page


# Feature pages. Each keeps its Stitch markup; data wiring lands per feature.
_simple_page("/talk", "pages/talk.html", "talk-to-nirvaan", "Talk to NIRVAAN")
_simple_page("/check", "pages/check_message.html", "check-a-message", "Check a Message")
_simple_page("/reflect", "pages/reflect.html", "pause-and-reflect", "Pause & Reflect")
_simple_page("/learn", "pages/learn.html", "learn-and-explore", "Learn & Explore")
_simple_page("/journey", "pages/journey.html", "my-journey", "My Journey")
_simple_page("/family", "pages/family.html", "family-mode", "Family Mode")
_simple_page("/privacy", "pages/privacy.html", "privacy-center", "Privacy Center")
_simple_page("/settings", "pages/settings.html", "settings", "Profile & Settings")
_simple_page("/offline", "pages/offline.html", "offline", "Offline Mode")
_simple_page("/batch", "pages/batch.html", "batch", "Batch Analysis")
_simple_page(
    "/decision-readiness",
    "pages/decision_readiness.html",
    "decision-readiness",
    "Decision Readiness",
)
_simple_page("/explain", "pages/explain_simply.html", "explain-simply", "Explain Simply")
_simple_page("/help", "pages/help.html", "help-and-support", "Help & Support")


@router.get("/admin", response_class=HTMLResponse)
def admin_console(request: Request, user: RequireAdmin, db: DbDep):
    """Operational console.

    Admins see aggregate metrics, health and system logs. They do not get
    access to private journals, memories, transcripts or analyses - that is
    enforced by the admin data routes, not by hiding links here.
    """
    from app.services.ai import registry

    return render(
        request,
        "pages/admin.html",
        user=user,
        db=db,
        active_nav="admin",
        provider_health=registry.health_report(),
        **_page_context("admin", db, user),
    )
