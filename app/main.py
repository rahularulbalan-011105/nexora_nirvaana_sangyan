"""NIRVAAN application entry point.

Run:  uvicorn app.main:app --reload
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR, settings
from app.db import SessionLocal
from app.deps import LoginRedirect, redirect_to_login
from app.routers import (
    api,
    auth,
    feature_account,
    feature_batch,
    feature_check,
    feature_learn,
    feature_reflect,
    pages,
    reports,
)
from app.templating import render

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("nirvaan")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    log.info("%s starting in %s mode", settings.app_name, settings.app_env)
    if settings.is_sqlite:
        log.warning(
            "Using the SQLite dev fallback. Set USE_SQLITE_FALLBACK=false and "
            "point DATABASE_URL at PostgreSQL before deploying."
        )
    if settings.is_production and settings.secret_key.startswith("dev-only"):
        raise RuntimeError(
            "SECRET_KEY is still the development default. Set a strong value "
            "before running in production."
        )
    if settings.is_production and not settings.cookie_secure:
        log.error("COOKIE_SECURE is false in production - cookies will be sent over HTTP.")

    from app.services.ai import registry

    for provider in registry.health_report():
        level = log.info if provider["healthy"] else log.warning
        level("AI provider %s: %s", provider["name"], provider["detail"])

    yield
    log.info("%s shutting down", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    description="Multilingual, voice-first AI financial resilience companion.",
    version="0.1.0",
    lifespan=lifespan,
    # The API docs expose route shapes; keep them out of production.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
)

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "app" / "static")),
    name="static",
)

app.include_router(auth.router)
app.include_router(api.router)
app.include_router(pages.router)
app.include_router(reports.router)
for _feature in (feature_check, feature_batch, feature_reflect, feature_learn, feature_account):
    app.include_router(_feature.router)


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)

    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        # Microphone is needed for the voice assistant; the rest is denied.
        "geolocation=(), camera=(), payment=(), usb=(), microphone=(self)",
    )
    # The service worker lives under /static/js/ but controls the whole site.
    if request.url.path == "/static/js/sw.js":
        response.headers["Service-Worker-Allowed"] = "/"
    if settings.is_production:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )

    # The Stitch design loads Tailwind and fonts from CDNs, so those hosts are
    # allowlisted explicitly rather than opening up script-src entirely.
    response.headers.setdefault(
        "Content-Security-Policy",
        "; ".join(
            [
                "default-src 'self'",
                "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com",
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
                "font-src 'self' https://fonts.gstatic.com",
                "img-src 'self' data: https:",
                "connect-src 'self'",
                "frame-ancestors 'none'",
                "base-uri 'self'",
                "form-action 'self'",
            ]
        ),
    )
    return response


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def _wants_json(request: Request) -> bool:
    if request.url.path.startswith("/api/"):
        return True
    accept = request.headers.get("accept", "")
    return "application/json" in accept and "text/html" not in accept


@app.exception_handler(LoginRedirect)
async def login_redirect_handler(_request: Request, exc: LoginRedirect):
    return redirect_to_login(exc.next_url)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if _wants_json(request):
        return JSONResponse(
            {"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers
        )

    # Browsers hitting a protected page without a session go to the login form.
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        return redirect_to_login(request.url.path)

    db = SessionLocal()
    try:
        from app.services.auth import resolve_session

        user = resolve_session(db, request.cookies.get(settings.session_cookie_name))
        return render(
            request,
            "pages/error.html",
            user=user,
            db=db,
            active_nav="",
            status_code=exc.status_code,
            status=exc.status_code,
            detail=exc.detail,
        )
    finally:
        db.close()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.exception("unhandled error on %s %s", request.method, request.url.path)

    if _wants_json(request):
        return JSONResponse(
            {"detail": "Something went wrong on our side. Please try again."},
            status_code=500,
        )

    db = SessionLocal()
    try:
        from app.services.auth import resolve_session

        user = resolve_session(db, request.cookies.get(settings.session_cookie_name))
        return render(
            request,
            "pages/error.html",
            user=user,
            db=db,
            active_nav="",
            status_code=500,
            status=500,
            detail="Something went wrong on our side. Please try again.",
            # The traceback is shown only in development.
            trace=repr(exc) if settings.debug else None,
        )
    except Exception:  # noqa: BLE001 - last resort if the error page itself fails
        return HTMLResponse(
            "<h1>NIRVAAN</h1><p>Something went wrong. Please try again.</p>",
            status_code=500,
        )
    finally:
        db.close()


@app.get("/healthz", include_in_schema=False)
def healthz():
    """Minimal liveness probe that touches nothing."""
    return {"status": "ok"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return RedirectResponse("/static/img/favicon.svg", status_code=301)
