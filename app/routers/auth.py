"""Authentication routes: register, login, logout, verify, reset."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import settings
from app.deps import CurrentUser, DbDep, ThrottleLogin, verify_csrf
from app.services import auth as auth_service
from app.services import audit, mail
from app.templating import render

router = APIRouter(tags=["auth"])

SESSION_COOKIE_KW = dict(
    httponly=True,
    secure=settings.cookie_secure,
    samesite=settings.cookie_samesite,
    path="/",
)


def _client(request: Request) -> tuple[str | None, str | None]:
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else None)
    )
    return ip, request.headers.get("user-agent")


def _safe_next(value: str | None) -> str:
    """Only allow same-site relative redirects, to stop open-redirects."""
    if not value or not value.startswith("/") or value.startswith("//"):
        return "/dashboard"
    return value


def _absolute(request: Request, path: str) -> str:
    return str(request.base_url).rstrip("/") + path


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user: CurrentUser, db: DbDep):
    if user is not None:
        return RedirectResponse("/dashboard", status_code=303)
    return render(
        request,
        "pages/login.html",
        db=db,
        active_nav="login",
        next_url=_safe_next(request.query_params.get("next")),
        notice=request.query_params.get("notice"),
    )


@router.post("/login", dependencies=[Depends(verify_csrf), ThrottleLogin])
def login_submit(
    request: Request,
    db: DbDep,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: Annotated[str, Form()] = "/dashboard",
):
    ip, user_agent = _client(request)
    result = auth_service.login(db, email=email, password=password, ip_address=ip, user_agent=user_agent)

    if not result.ok or result.user is None:
        audit.record(
            db,
            action="auth.login.failed",
            outcome="failure",
            request=request,
            detail={"email_attempted": auth_service.normalise_email(email)},
        )
        db.commit()
        return render(
            request,
            "pages/login.html",
            db=db,
            active_nav="login",
            status_code=401,
            errors=result.errors,
            email_value=email,
            next_url=_safe_next(next),
        )

    audit.record(
        db, action="auth.login", user_id=result.user.id, request=request
    )
    db.commit()

    response = RedirectResponse(_safe_next(next), status_code=303)
    response.set_cookie(
        settings.session_cookie_name,
        result.session_token or "",
        max_age=settings.session_ttl_hours * 3600,
        **SESSION_COOKIE_KW,
    )
    return response


@router.post("/logout", dependencies=[Depends(verify_csrf)])
def logout(
    request: Request,
    db: DbDep,
    user: CurrentUser,
    all_devices: Annotated[str, Form(alias="all")] = "",
):
    token = request.cookies.get(settings.session_cookie_name)
    auth_service.revoke_session(db, token)
    if user is not None:
        if all_devices == "1":
            auth_service.revoke_all_sessions(db, user)
        audit.record(db, action="auth.logout", user_id=user.id, request=request)
    db.commit()

    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(settings.session_cookie_name, path="/")
    return response


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, user: CurrentUser, db: DbDep):
    if user is not None:
        return RedirectResponse("/dashboard", status_code=303)
    return render(request, "pages/register.html", db=db, active_nav="register")


@router.post("/register", dependencies=[Depends(verify_csrf), ThrottleLogin])
def register_submit(
    request: Request,
    db: DbDep,
    full_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    language: Annotated[str, Form()] = "en",
    gender: Annotated[str, Form()] = "",
):
    result = auth_service.register(
        db,
        full_name=full_name,
        email=email,
        password=password,
        language=language,
        gender=gender or None,
    )

    if not result.ok or result.user is None:
        return render(
            request,
            "pages/register.html",
            db=db,
            active_nav="register",
            status_code=400,
            errors=result.errors,
            name_value=full_name,
            email_value=email,
            language_value=language,
            gender_value=gender,
        )

    new_user = result.user
    token = auth_service.issue_email_verification(db, new_user)
    mail.send_verification(
        to=new_user.email,
        name=new_user.first_name,
        link=_absolute(request, f"/verify-email?token={token}"),
    )

    audit.record(db, action="auth.register", user_id=new_user.id, request=request)

    # Sign the new account in directly; email confirmation gates sharing
    # features rather than blocking all access.
    ip, user_agent = _client(request)
    session_token = auth_service.create_session(
        db, new_user, ip_address=ip, user_agent=user_agent
    )
    db.commit()

    response = RedirectResponse("/dashboard?welcome=1", status_code=303)
    response.set_cookie(
        settings.session_cookie_name,
        session_token,
        max_age=settings.session_ttl_hours * 3600,
        **SESSION_COOKIE_KW,
    )
    return response


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------


@router.get("/verify-email", response_class=HTMLResponse)
def verify_email(request: Request, db: DbDep, user: CurrentUser, token: str = ""):
    if not token:
        return render(
            request,
            "pages/verify_email.html",
            db=db,
            user=user,
            active_nav="verify",
            pending=True,
        )

    result = auth_service.consume_email_verification(db, token)
    if result.ok and result.user is not None:
        audit.record(
            db, action="auth.email_verified", user_id=result.user.id, request=request
        )
    db.commit()

    return render(
        request,
        "pages/verify_email.html",
        db=db,
        user=user,
        active_nav="verify",
        verified=result.ok,
        errors=result.errors,
    )


@router.post("/verify-email/resend", dependencies=[Depends(verify_csrf), ThrottleLogin])
def resend_verification(request: Request, db: DbDep, user: CurrentUser):
    if user is not None and user.email_verified_at is None:
        token = auth_service.issue_email_verification(db, user)
        mail.send_verification(
            to=user.email,
            name=user.first_name,
            link=_absolute(request, f"/verify-email?token={token}"),
        )
        audit.record(
            db, action="auth.verification_resent", user_id=user.id, request=request
        )
        db.commit()
    return RedirectResponse("/verify-email?notice=sent", status_code=303)


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request, db: DbDep):
    return render(request, "pages/forgot_password.html", db=db, active_nav="forgot")


@router.post("/forgot-password", dependencies=[Depends(verify_csrf), ThrottleLogin])
def forgot_password_submit(
    request: Request, db: DbDep, email: Annotated[str, Form()]
):
    user, token = auth_service.issue_password_reset(db, email)
    if user is not None and token is not None:
        mail.send_password_reset(
            to=user.email,
            name=user.first_name,
            link=_absolute(request, f"/reset-password?token={token}"),
        )
        audit.record(
            db, action="auth.reset_requested", user_id=user.id, request=request
        )
    else:
        audit.record(
            db,
            action="auth.reset_requested",
            outcome="no_account",
            request=request,
            detail={"email_attempted": auth_service.normalise_email(email)},
        )
    db.commit()

    # Identical response either way, so the form cannot enumerate accounts.
    return render(
        request,
        "pages/forgot_password.html",
        db=db,
        active_nav="forgot",
        notice=(
            "If an account exists for that address, a reset link is on its way. "
            "Please check your inbox, including the spam folder."
        ),
        submitted=True,
    )


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request, db: DbDep, token: str = ""):
    return render(
        request,
        "pages/reset_password.html",
        db=db,
        active_nav="reset",
        token=token,
        errors=[] if token else ["That reset link is missing its token."],
    )


@router.post("/reset-password", dependencies=[Depends(verify_csrf), ThrottleLogin])
def reset_password_submit(
    request: Request,
    db: DbDep,
    token: Annotated[str, Form()],
    password: Annotated[str, Form()],
    confirm_password: Annotated[str, Form()] = "",
):
    if confirm_password and password != confirm_password:
        return render(
            request,
            "pages/reset_password.html",
            db=db,
            active_nav="reset",
            status_code=400,
            token=token,
            errors=["The two passwords do not match."],
        )

    result = auth_service.reset_password(db, raw_token=token, new_password=password)
    if not result.ok:
        db.commit()
        return render(
            request,
            "pages/reset_password.html",
            db=db,
            active_nav="reset",
            status_code=400,
            token=token,
            errors=result.errors,
        )

    if result.user is not None:
        audit.record(
            db, action="auth.password_reset", user_id=result.user.id, request=request
        )
    db.commit()

    response = RedirectResponse(
        "/login?notice=Your+password+has+been+updated.+Please+sign+in.",
        status_code=303,
    )
    # Every old session was revoked; clear this browser's cookie too.
    response.delete_cookie(settings.session_cookie_name, path="/")
    return response
