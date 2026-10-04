"""CSRF protection for the server-rendered form posts.

Double-submit cookie pattern: a random value is set in a cookie and must be
echoed back in a hidden ``_csrf`` form field (or the ``X-CSRF-Token`` header
for fetch calls). Both halves are compared in constant time.
"""
from __future__ import annotations

import hmac
import secrets

from fastapi import Request, Response

from app.config import settings

FIELD_NAME = "_csrf"
HEADER_NAME = "X-CSRF-Token"

# Methods that cannot change state need no token.
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def issue_token(response: Response) -> str:
    """Mint a CSRF token and attach it to the response as a readable cookie."""
    token = secrets.token_urlsafe(32)
    response.set_cookie(
        settings.csrf_cookie_name,
        token,
        max_age=60 * 60 * 12,
        # Readable by JS on purpose: fetch() needs to echo it in the header.
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
    return token


def get_or_issue(request: Request, response: Response) -> str:
    existing = request.cookies.get(settings.csrf_cookie_name)
    if existing:
        return existing
    return issue_token(response)


async def validate(request: Request) -> bool:
    """True when the submitted token matches the cookie."""
    if request.method.upper() in SAFE_METHODS:
        return True

    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    if not cookie_token:
        return False

    submitted = request.headers.get(HEADER_NAME)
    if not submitted:
        content_type = request.headers.get("content-type", "")
        if "form" in content_type:
            # Starlette caches the parsed body, so the route can read it again.
            form = await request.form()
            value = form.get(FIELD_NAME)
            submitted = value if isinstance(value, str) else None

    if not submitted:
        return False
    return hmac.compare_digest(submitted, cookie_token)
