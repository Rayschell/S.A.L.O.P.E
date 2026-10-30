"""Authentication router — JWT en cookies httpOnly."""
from __future__ import annotations

import time
from typing import Optional
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..core.deps import get_current_member, get_db
from ..core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from ..models.models import Member
from ..schemas.schemas import LoginRequest, MemberRead
from ..services.google_auth import email_allowed, oauth, provision_member

router = APIRouter(prefix="/api/auth", tags=["auth"])

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"

# Rate-limit login : 5 tentatives / minute / IP (in-memory — suffisant en mono-réplique)
_LOGIN_ATTEMPTS: dict[str, deque] = defaultdict(deque)
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 60.0


def _check_login_rate_limit(ip: str) -> None:
    now = time.monotonic()
    attempts = _LOGIN_ATTEMPTS[ip]
    while attempts and now - attempts[0] > _LOGIN_WINDOW_SECONDS:
        attempts.popleft()
    if len(attempts) >= _LOGIN_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives de connexion. Réessayez dans une minute.",
        )
    attempts.append(now)


def _set_auth_cookies(response: Response, member_id: int) -> None:
    response.set_cookie(
        ACCESS_COOKIE,
        create_access_token(member_id),
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/api",
    )
    # Le refresh token n'est envoyé qu'aux endpoints d'auth
    response.set_cookie(
        REFRESH_COOKIE,
        create_refresh_token(member_id),
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/auth",
    )


@router.post("/login", response_model=MemberRead)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _check_login_rate_limit(request.client.host if request.client else "unknown")

    member = db.query(Member).filter(Member.email == payload.email).first()
    if not member or not member.hashed_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not verify_password(payload.password, member.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Domain check
    domain = payload.email.split("@")[-1].lower()
    if domain != settings.ALLOWED_EMAIL_DOMAIN.lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email domain not allowed")

    _set_auth_cookies(response, member.id)
    return member


_NEXT_ALLOWED = "/api/oauth/authorize"


def safe_next(value: Optional[str]) -> Optional[str]:
    """`next` post-login : uniquement l'authorize OAuth du MCP (anti open-redirect)."""
    if not value or "\\" in value:
        return None
    if value == _NEXT_ALLOWED or value.startswith(_NEXT_ALLOWED + "?"):
        return value
    return None


@router.get("/google/login")
async def google_login(request: Request, next: Optional[str] = None):
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google login not configured")
    # Retour vers l'authorize OAuth du MCP après le login, si demandé
    request.session.pop("next", None)
    if safe_next(next):
        request.session["next"] = safe_next(next)
    return await oauth.google.authorize_redirect(
        request,
        settings.GOOGLE_REDIRECT_URI,
        hd=settings.ALLOWED_EMAIL_DOMAIN,  # simple indice UX, le contrôle réel est fait au callback
    )


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    def fail(code: str) -> RedirectResponse:
        return RedirectResponse(f"/login?error={code}", status_code=status.HTTP_303_SEE_OTHER)

    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        return fail("oidc")

    info = token.get("userinfo") or {}
    email = (info.get("email") or "").lower()
    if not email or not info.get("email_verified"):
        return fail("email")
    if not email_allowed(email) or info.get("hd", "").lower() != settings.ALLOWED_EMAIL_DOMAIN.lower():
        return fail("domain")

    member = provision_member(db, email, info.get("given_name"), info.get("family_name"))
    target = safe_next(request.session.pop("next", None)) or "/"
    response = RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)
    _set_auth_cookies(response, member.id)
    return response


@router.post("/refresh", response_model=MemberRead)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    token = request.cookies.get(REFRESH_COOKIE)
    member_id = decode_token(token, expected_type="refresh") if token else None
    if member_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Member not found")
    _set_auth_cookies(response, member.id)
    return member


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    response.delete_cookie(ACCESS_COOKIE, path="/api")
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")


@router.get("/me", response_model=MemberRead)
def me(current: Member = Depends(get_current_member)):
    return current
