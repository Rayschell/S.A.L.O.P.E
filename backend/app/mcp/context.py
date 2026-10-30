"""Accès base du serveur MCP.

Le middleware et les tools passent par `context.open_session()` (accès via le
module) pour que les tests puissent substituer leur session transactionnelle.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm import Session

from ..database import SessionLocal


@contextmanager
def open_session() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
