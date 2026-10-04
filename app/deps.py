"""Shared FastAPI dependencies: database, current user, guards, rate limits."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.db import get_db
from app.models.enums import Role
from app.models.user import User
from app.security import csrf
from app.security.ratelimit import RedisRateLimiter, client_key
from app.security.rbac import Forbidden, Unauthorized, require_roles
from app.services import auth

DbDep = Annotated[DbSession, Depends(get_db)]

# Shared limiter instances. Login is throttled far harder than general reads.
# Counted in Redis when REDIS_URL is set and reachable (shared by every
# worker); otherwise per process, in memory.
login_limiter = RedisRateLimiter(
    "login", limit=settings.rate_limit_login_per_min, window_seconds=60
)
api_limiter = RedisRateLimiter("api", limit=settings.rate_limit_api_per_min, window_seconds=60)


class LoginRedirect(HTTPException):
    """Signals the error handler to send a browser to /login."""

    def __init__(self, next_url: str = "/") -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED)
        self.next_url = next_url


def current_user(request: Request, db: DbDep) -> User | None:
    """Resolve the signed-in user, or None. Never raises."""
    # Cached per request so several dependencies do not re-query.
    cached = getattr(request.state, "user", None)
    if cached is not None:
        return cached

    token = request.cookies.get(settings.session_cookie_name)
    user = auth.resolve_session(db, token)
    request.state.user = user
    return user


CurrentUser = Annotated[User | None, Depends(current_user)]


def require_user(request: Request, user: CurrentUser) -> User:
    """Protected-route guard. Browsers get a redirect; APIs get a 401."""
    if user is None:
        if _wants_html(request):
            raise LoginRedirect(next_url=str(request.url.path))
        raise Unauthorized()
    return user


RequireUser = Annotated[User, Depends(require_user)]


def require_admin_user(user: RequireUser) -> User:
    return require_roles(user, Role.ADMIN)


RequireAdmin = Annotated[User, Depends(require_admin_user)]


def require_verified_user(user: RequireUser) -> User:
    """For actions that should wait until the address is confirmed.

    Reading and learning stay open to unverified accounts; this guards the
    paths that send mail or share data with another person.
    """
    if user.email_verified_at is None:
        raise Forbidden("Please confirm your email address to use this feature.")
    return user


RequireVerified = Annotated[User, Depends(require_verified_user)]


async def verify_csrf(request: Request) -> None:
    """Dependency for every state-changing route."""
    if not await csrf.validate(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your form session expired. Please reload the page and try again.",
        )


CsrfProtected = Depends(verify_csrf)


def throttle_login(request: Request) -> None:
    allowed, retry_after = login_limiter.check(client_key(request, "login"))
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please wait a moment before trying again.",
            headers={"Retry-After": str(retry_after)},
        )


def throttle_api(request: Request) -> None:
    allowed, retry_after = api_limiter.check(client_key(request, "api"))
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You are sending requests very quickly. Please slow down.",
            headers={"Retry-After": str(retry_after)},
        )


ThrottleLogin = Depends(throttle_login)
ThrottleApi = Depends(throttle_api)


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    if request.url.path.startswith("/api/"):
        return False
    return "text/html" in accept or accept in ("", "*/*")


def redirect_to_login(next_url: str = "/") -> RedirectResponse:
    target = "/login"
    if next_url and next_url not in ("/", "/login"):
        from urllib.parse import quote

        target = f"/login?next={quote(next_url, safe='')}"
    return RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)
