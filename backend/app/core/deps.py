"""FastAPI dependency helpers."""
from __future__ import annotations

from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from ..core.security import decode_token
from ..database import SessionLocal
from ..models.models import Member

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_member(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Member:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    member_id = decode_token(token, expected_type="access")
    if member_id is None:
        raise credentials_exc
    member = db.query(Member).filter(Member.id == member_id).first()
    if member is None:
        raise credentials_exc
    return member


def require_bureau(current: Member = Depends(get_current_member)) -> Member:
    """Restrict endpoint to bureau members."""
    if not current.roles or "bureau" not in current.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bureau role required",
        )
    return current
