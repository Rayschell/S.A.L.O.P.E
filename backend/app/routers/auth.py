"""Authentication router."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
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
from ..schemas.schemas import LoginRequest, MemberRead, RefreshRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    member = db.query(Member).filter(Member.email == payload.email).first()
    if not member or not member.hashed_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not verify_password(payload.password, member.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Domain check
    domain = payload.email.split("@")[-1].lower()
    if domain != settings.ALLOWED_EMAIL_DOMAIN.lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email domain not allowed")

    return TokenResponse(
        access_token=create_access_token(member.id),
        refresh_token=create_refresh_token(member.id),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    member_id = decode_token(payload.refresh_token, expected_type="refresh")
    if member_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Member not found")
    return TokenResponse(
        access_token=create_access_token(member.id),
        refresh_token=create_refresh_token(member.id),
    )


@router.get("/me", response_model=MemberRead)
def me(current: Member = Depends(get_current_member)):
    return current
