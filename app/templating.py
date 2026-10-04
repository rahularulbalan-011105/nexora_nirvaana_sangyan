"""Jinja environment and the shared render context.

Every page render goes through ``render``, which supplies the variables the
generated Stitch shell expects: nav items and active state, the signed-in
user, language, preferences, CSRF token and the translator ``t``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.config import BASE_DIR
from app import navigation
from app.models.user import User
from app.security import csrf
from app.services import i18n, ui_translate

TEMPLATE_DIR = BASE_DIR / "app" / "templates"

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# Helpers available inside every template.
templates.env.globals.update(
    nav_active_class=navigation.NAV_ACTIVE_CLASS,
    nav_inactive_class=navigation.NAV_INACTIVE_CLASS,
    language_options=i18n.language_options(),
    now=lambda: datetime.now(timezone.utc),
)
# Blank rather than "None" for missing values in the copied Stitch markup.
templates.env.finalize = lambda value: "" if value is None else value


def greeting_key(moment: datetime | None = None) -> str:
    hour = (moment or datetime.now()).hour
    if hour < 12:
        return "greeting.morning"
    if hour < 17:
        return "greeting.afternoon"
    return "greeting.evening"


def _unread_count(db: DbSession | None, user: User | None) -> int:
    if db is None or user is None:
        return 0
    from app.models.system import Notification

    return int(
        db.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        ).scalar()
        or 0
    )


def resolve_language(request: Request, user: User | None) -> str:
    """Language precedence: explicit query, cookie, user preference, header."""
    requested = request.query_params.get("lang")
    if requested:
        return i18n.normalise(requested)

    cookie = request.cookies.get("nirvaan_lang")
    if cookie:
        return i18n.normalise(cookie)

    if user is not None and user.preferences is not None:
        return i18n.normalise(user.preferences.language)

    header = request.headers.get("accept-language", "")
    for part in header.split(","):
        code = i18n.normalise(part.split(";")[0].strip())
        if code != i18n.DEFAULT_LANGUAGE:
            return code
    return i18n.DEFAULT_LANGUAGE


def _recent_notifications(db: DbSession | None, user: User | None) -> list[Any]:
    if db is None or user is None:
        return []
    from app.models.system import Notification

    return list(
        db.execute(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(6)
        ).scalars()
    )


def base_context(
    request: Request,
    *,
    user: User | None = None,
    db: DbSession | None = None,
    active_nav: str = "dashboard",
    **extra: Any,
) -> dict[str, Any]:
    """Build the context the shell templates rely on."""
    language = resolve_language(request, user)
    prefs = user.preferences if user is not None else None

    context: dict[str, Any] = {
        "request": request,
        "user": user,
        "prefs": prefs,
        "privacy": user.privacy if user is not None else None,
        "lang_code": language,
        "language_label": i18n.language_label(language),
        "t": i18n.translator(language),
        "nav_items": navigation.items_for(user),
        "active_nav": active_nav,
        "breadcrumb": navigation.breadcrumb_for(active_nav),
        "unread_count": _unread_count(db, user),
        "notifications": _recent_notifications(db, user),
        "user_status": "Learning • Growing" if user else "Not signed in",
        "search_placeholder": (
            "Ask anything about financial information... "
            "(e.g. SIP, mutual funds, scam check)"
        ),
        "greeting": i18n.translate(
            greeting_key(), language, name=user.first_name if user else "there"
        ),
        "is_admin": bool(user and user.is_admin),
    }
    context.update(extra)
    return context


def render(
    request: Request,
    template: str,
    *,
    user: User | None = None,
    db: DbSession | None = None,
    active_nav: str = "dashboard",
    status_code: int = 200,
    **extra: Any,
) -> HTMLResponse:
    """Render a page template with the shared context and a CSRF token."""
    response = HTMLResponse(content="", status_code=status_code)
    token = csrf.get_or_issue(request, response)

    context = base_context(
        request, user=user, db=db, active_nav=active_nav, csrf_token=token, **extra
    )
    body = templates.get_template(template).render(context)

    if context["lang_code"] != i18n.DEFAULT_LANGUAGE:
        body = ui_translate.translate_html(body, context["lang_code"])

    # Build the final response, carrying over the CSRF cookie just set.
    final = HTMLResponse(content=body, status_code=status_code)
    for key, value in response.raw_headers:
        if key.decode().lower() == "set-cookie":
            final.raw_headers.append((key, value))

    language = context["lang_code"]
    if request.query_params.get("lang"):
        final.set_cookie(
            "nirvaan_lang",
            language,
            max_age=60 * 60 * 24 * 365,
            httponly=False,
            samesite="lax",
            path="/",
        )
    return final
