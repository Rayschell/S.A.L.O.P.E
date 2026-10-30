"""Tables OAuth du serveur MCP."""
from __future__ import annotations

from datetime import datetime


def test_oauth_tables_roundtrip(db_session, bureau_member):
    from app.models.models import OAuthClient, OAuthToken

    client = OAuthClient(client_id="c1", redirect_uris=["http://localhost:1/cb"])
    db_session.add(client)
    db_session.flush()
    db_session.add(
        OAuthToken(
            token_hash="h1",
            type="access",
            client_id="c1",
            membre_id=bureau_member.id,
            family_id="f1",
            expires_at=datetime(2030, 1, 1),
        )
    )
    db_session.flush()

    assert db_session.get(OAuthClient, "c1").redirect_uris == ["http://localhost:1/cb"]
    assert db_session.query(OAuthToken).filter_by(token_hash="h1").count() == 1

    db_session.delete(client)
    db_session.flush()
    db_session.expire_all()
    assert db_session.query(OAuthToken).filter_by(token_hash="h1").count() == 0
