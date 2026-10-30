"""Shared pytest fixtures for the backend test suite."""
from __future__ import annotations

import os
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

# Default: postgres from docker-compose on port 5433, base salope_test
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://baruser:barpassword@localhost:5433/salope_test",
)

# Derive the admin URL (connect to the default "salope" DB to create salope_test)
_ADMIN_URL = TEST_DATABASE_URL.rsplit("/", 1)[0] + "/salope"

# ---------------------------------------------------------------------------
# Session-scope: create DB + tables once, drop_all at teardown
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def test_engine():
    # Create the test database if it doesn't exist
    admin_engine = create_engine(_ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'salope_test'")
        ).fetchone()
        if not exists:
            conn.execute(text("CREATE DATABASE salope_test"))
    admin_engine.dispose()

    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)

    # Import Base after engine is configured (avoids importing app config too early)
    from app.database import Base
    import app.models.models  # noqa: F401 — registers all models on Base

    Base.metadata.create_all(bind=engine)

    yield engine

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


# ---------------------------------------------------------------------------
# Per-test: connection + nested transaction (SAVEPOINT) → rollback isolation
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session(test_engine) -> Generator[Session, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()

    TestingSession = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = TestingSession()

    # Create a SAVEPOINT so each test can roll back cleanly
    nested = connection.begin_nested()

    yield session

    session.close()
    if nested.is_active:
        nested.rollback()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# Bureau member fixture (shared by client fixture)
# ---------------------------------------------------------------------------


@pytest.fixture()
def bureau_member(db_session: Session):
    from app.models.models import Member

    member = Member(
        nom="Test",
        prenom="Bureau",
        email="bureau@lateb.eu",
        roles=["bureau", "staff"],
        shifts_respo_bar_cumules=0,
    )
    db_session.add(member)
    db_session.flush()
    return member


# ---------------------------------------------------------------------------
# TestClient fixture with overridden dependencies
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(db_session: Session, bureau_member) -> TestClient:
    from app.main import app
    from app.core.deps import get_db, get_current_member, require_bureau

    def override_get_db():
        yield db_session

    def override_auth():
        return bureau_member

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_member] = override_auth
    app.dependency_overrides[require_bureau] = override_auth

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _reset_register_rate_limit():
    """Le rate-limit DCR est in-memory et par IP : tous les tests partagent l'IP du TestClient."""
    from app.routers import oauth

    oauth._REGISTER_ATTEMPTS.clear()
    yield
    oauth._REGISTER_ATTEMPTS.clear()
