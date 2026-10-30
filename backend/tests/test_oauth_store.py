"""Service oauth_store : DCR, PKCE, tokens opaques MCP."""
from __future__ import annotations

import base64
import hashlib
from datetime import timedelta

import pytest

from app.services import oauth_store
from app.services.oauth_store import OAuthError

REDIRECT = "http://localhost:33418/callback"
VERIFIER = "a" * 50


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


@pytest.fixture()
def oauth_client(db_session):
    return oauth_store.register_client(db_session, "Claude Code", [REDIRECT])


@pytest.fixture()
def shift_now(monkeypatch):
    def _shift(delta: timedelta):
        target = oauth_store._now() + delta
        monkeypatch.setattr(oauth_store, "_now", lambda: target)

    return _shift


def _code(db, client, member):
    return oauth_store.issue_code(
        db, client, member.id, REDIRECT, _challenge(VERIFIER), None
    )


def test_register_rejects_unknown_redirect(db_session):
    with pytest.raises(OAuthError) as exc:
        oauth_store.register_client(db_session, "Evil", ["https://evil.com/cb"])
    assert exc.value.error == "invalid_redirect_uri"


def test_register_rejects_empty_redirects(db_session):
    with pytest.raises(OAuthError) as exc:
        oauth_store.register_client(db_session, "Vide", [])
    assert exc.value.error == "invalid_redirect_uri"


def test_register_accepts_claude_ai(db_session):
    client = oauth_store.register_client(
        db_session, "Claude", ["https://claude.ai/api/mcp/auth_callback"]
    )
    assert oauth_store.get_client(db_session, client.client_id) is not None


def test_loopback_port_free():
    registered = ["http://localhost:33418/callback"]
    assert oauth_store.redirect_uri_matches(registered, "http://localhost:51000/callback")
    assert not oauth_store.redirect_uri_matches(registered, "http://evil.com:51000/callback")
    assert not oauth_store.redirect_uri_matches(registered, "http://localhost:51000/other")


def test_non_loopback_exact_match():
    registered = ["https://claude.ai/api/mcp/auth_callback"]
    assert oauth_store.redirect_uri_matches(registered, registered[0])
    assert not oauth_store.redirect_uri_matches(
        registered, "https://claude.ai:8443/api/mcp/auth_callback"
    )


def test_code_exchange_ok(db_session, oauth_client, bureau_member):
    code = _code(db_session, oauth_client, bureau_member)
    pair = oauth_store.exchange_code(
        db_session, oauth_client.client_id, code, REDIRECT, VERIFIER
    )
    assert pair.expires_in == 3600
    member = oauth_store.member_for_access_token(db_session, pair.access_token)
    assert member.id == bureau_member.id


def test_code_bad_verifier(db_session, oauth_client, bureau_member):
    code = _code(db_session, oauth_client, bureau_member)
    with pytest.raises(OAuthError) as exc:
        oauth_store.exchange_code(
            db_session, oauth_client.client_id, code, REDIRECT, "b" * 50
        )
    assert exc.value.error == "invalid_grant"


def test_code_single_use(db_session, oauth_client, bureau_member):
    code = _code(db_session, oauth_client, bureau_member)
    oauth_store.exchange_code(db_session, oauth_client.client_id, code, REDIRECT, VERIFIER)
    with pytest.raises(OAuthError) as exc:
        oauth_store.exchange_code(
            db_session, oauth_client.client_id, code, REDIRECT, VERIFIER
        )
    assert exc.value.error == "invalid_grant"


def test_code_expired(db_session, oauth_client, bureau_member, shift_now):
    code = _code(db_session, oauth_client, bureau_member)
    shift_now(timedelta(minutes=6))
    with pytest.raises(OAuthError) as exc:
        oauth_store.exchange_code(
            db_session, oauth_client.client_id, code, REDIRECT, VERIFIER
        )
    assert exc.value.error == "invalid_grant"


def test_code_wrong_redirect_uri(db_session, oauth_client, bureau_member):
    code = _code(db_session, oauth_client, bureau_member)
    with pytest.raises(OAuthError) as exc:
        oauth_store.exchange_code(
            db_session, oauth_client.client_id, code, "http://localhost:1/autre", VERIFIER
        )
    assert exc.value.error == "invalid_grant"


def test_code_other_client(db_session, oauth_client, bureau_member):
    other = oauth_store.register_client(db_session, "Autre", [REDIRECT])
    code = _code(db_session, oauth_client, bureau_member)
    with pytest.raises(OAuthError) as exc:
        oauth_store.exchange_code(db_session, other.client_id, code, REDIRECT, VERIFIER)
    assert exc.value.error == "invalid_grant"


def test_refresh_rotates(db_session, oauth_client, bureau_member):
    first = oauth_store.issue_tokens(db_session, oauth_client.client_id, bureau_member.id)
    second = oauth_store.refresh_tokens(
        db_session, oauth_client.client_id, first.refresh_token
    )
    assert second.refresh_token != first.refresh_token
    assert oauth_store.member_for_access_token(db_session, second.access_token) is not None

    with pytest.raises(OAuthError) as exc:
        oauth_store.refresh_tokens(db_session, oauth_client.client_id, first.refresh_token)
    assert exc.value.error == "invalid_grant"
    # Réutilisation détectée : toute la famille est révoquée
    assert oauth_store.member_for_access_token(db_session, second.access_token) is None


def test_refresh_expired(db_session, oauth_client, bureau_member, shift_now):
    pair = oauth_store.issue_tokens(db_session, oauth_client.client_id, bureau_member.id)
    shift_now(timedelta(days=31))
    with pytest.raises(OAuthError) as exc:
        oauth_store.refresh_tokens(db_session, oauth_client.client_id, pair.refresh_token)
    assert exc.value.error == "invalid_grant"


def test_access_token_is_not_refresh(db_session, oauth_client, bureau_member):
    pair = oauth_store.issue_tokens(db_session, oauth_client.client_id, bureau_member.id)
    assert oauth_store.member_for_access_token(db_session, pair.refresh_token) is None
    with pytest.raises(OAuthError):
        oauth_store.refresh_tokens(db_session, oauth_client.client_id, pair.access_token)


def test_access_expired(db_session, oauth_client, bureau_member, shift_now):
    pair = oauth_store.issue_tokens(db_session, oauth_client.client_id, bureau_member.id)
    shift_now(timedelta(minutes=61))
    assert oauth_store.member_for_access_token(db_session, pair.access_token) is None


def test_revoke(db_session, oauth_client, bureau_member):
    pair = oauth_store.issue_tokens(db_session, oauth_client.client_id, bureau_member.id)
    oauth_store.revoke_token(db_session, pair.access_token)
    assert oauth_store.member_for_access_token(db_session, pair.access_token) is None
    oauth_store.revoke_token(db_session, "inconnu")  # pas d'erreur


def test_tokens_stored_hashed(db_session, oauth_client, bureau_member):
    from app.models.models import OAuthToken

    pair = oauth_store.issue_tokens(db_session, oauth_client.client_id, bureau_member.id)
    hashes = {t.token_hash for t in db_session.query(OAuthToken)}
    assert pair.access_token not in hashes
    assert oauth_store.hash_secret(pair.access_token) in hashes


def test_web_jwt_not_accepted(db_session, bureau_member):
    from app.core.security import create_access_token

    jwt = create_access_token(bureau_member.id)
    assert oauth_store.member_for_access_token(db_session, jwt) is None


@pytest.mark.parametrize(
    "uri",
    [
        "http://127.0.0.1:80@evil.com/cb",
        "http://localhost:1@evil.com/cb",
        "http://user:pw@localhost:1234/cb",
        "http://localhost:abc/cb",
        "http://localhost.evil.com:1234/cb",
    ],
)
def test_register_rejects_disguised_loopback(db_session, uri):
    assert not oauth_store.redirect_uri_allowed(uri)
    with pytest.raises(OAuthError):
        oauth_store.register_client(db_session, "Claude Code", [uri])


def test_register_accepts_ipv6_loopback(db_session):
    assert oauth_store.redirect_uri_allowed("http://[::1]:5000/callback")


def test_matches_rejects_userinfo():
    assert not oauth_store.redirect_uri_matches(
        ["http://localhost:1/cb"], "http://localhost:2@evil.com/cb"
    )


def test_purge_expired(db_session, oauth_client, bureau_member, shift_now):
    from app.models.models import OAuthAuthorizationCode, OAuthClient, OAuthToken

    _code(db_session, oauth_client, bureau_member)
    used = oauth_store.issue_tokens(db_session, oauth_client.client_id, bureau_member.id)
    # Refresh consommé (révoqué) mais non expiré : à garder pour détecter sa réutilisation
    oauth_store.refresh_tokens(db_session, oauth_client.client_id, used.refresh_token)
    orphan = oauth_store.register_client(db_session, "Orphelin", [REDIRECT])

    shift_now(timedelta(days=2))  # codes et access expirés, refresh (30 j) encore valides
    orphan.created_at = oauth_store._now() - timedelta(days=2)
    db_session.flush()
    oauth_store.purge_expired(db_session)

    assert db_session.query(OAuthAuthorizationCode).count() == 0
    assert {t.type for t in db_session.query(OAuthToken)} == {"refresh"}
    revoked = db_session.query(OAuthToken).filter(
        OAuthToken.token_hash == oauth_store.hash_secret(used.refresh_token)
    ).one()
    assert revoked.revoked_at is not None
    # Le client actif (refresh encore valides) reste, l'orphelin disparaît
    remaining = {c for (c,) in db_session.query(OAuthClient.client_id)}
    assert oauth_client.client_id in remaining
    assert orphan.client_id not in remaining
