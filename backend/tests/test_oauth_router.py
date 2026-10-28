"""Endpoints OAuth : metadata, register, token, revoke."""
from __future__ import annotations

import base64
import hashlib

from app.services import oauth_store

REDIRECT = "http://localhost:33418/callback"
VERIFIER = "v" * 64


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _register(client) -> str:
    r = client.post(
        "/api/oauth/register",
        json={"client_name": "Claude Code", "redirect_uris": [REDIRECT]},
    )
    assert r.status_code == 201, r.text
    return r.json()["client_id"]


def test_protected_resource_metadata(client):
    r = client.get("/.well-known/oauth-protected-resource/api/mcp")
    assert r.status_code == 200
    body = r.json()
    assert body["resource"] == "http://localhost:3000/api/mcp"
    assert body["authorization_servers"] == ["http://localhost:3000"]


def test_as_metadata(client):
    r = client.get("/.well-known/oauth-authorization-server")
    assert r.status_code == 200
    body = r.json()
    assert body["issuer"] == "http://localhost:3000"
    assert body["code_challenge_methods_supported"] == ["S256"]
    assert body["token_endpoint"] == "http://localhost:3000/api/oauth/token"
    assert body["registration_endpoint"] == "http://localhost:3000/api/oauth/register"
    assert client.get("/.well-known/openid-configuration").json() == body


def test_register_ok(client):
    r = client.post(
        "/api/oauth/register",
        json={"client_name": "Claude Code", "redirect_uris": [REDIRECT]},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["client_id"]
    assert body["token_endpoint_auth_method"] == "none"
    assert body["redirect_uris"] == [REDIRECT]


def test_register_bad_uri(client):
    r = client.post(
        "/api/oauth/register",
        json={"client_name": "Evil", "redirect_uris": ["https://evil.com/cb"]},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_redirect_uri"


def test_register_malformed_body(client):
    r = client.post("/api/oauth/register", json={"client_name": "X"})
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_redirect_uri"


def test_token_authorization_code(client, db_session, bureau_member):
    client_id = _register(client)
    oc = oauth_store.get_client(db_session, client_id)
    code = oauth_store.issue_code(
        db_session, oc, bureau_member.id, REDIRECT, _challenge(VERIFIER), None
    )
    r = client.post(
        "/api/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "redirect_uri": REDIRECT,
            "code_verifier": VERIFIER,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 3600
    assert body["access_token"] and body["refresh_token"]
    assert r.headers["cache-control"] == "no-store"


def test_token_bad_code(client):
    client_id = _register(client)
    r = client.post(
        "/api/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": "faux",
            "redirect_uri": REDIRECT,
            "code_verifier": VERIFIER,
        },
    )
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_grant"


def test_token_unknown_client(client):
    r = client.post(
        "/api/oauth/token",
        data={"grant_type": "refresh_token", "client_id": "nope", "refresh_token": "x"},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_client"


def test_token_refresh(client, db_session, bureau_member):
    client_id = _register(client)
    pair = oauth_store.issue_tokens(db_session, client_id, bureau_member.id)
    r = client.post(
        "/api/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": pair.refresh_token,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["refresh_token"] != pair.refresh_token


def test_token_bad_grant_type(client):
    client_id = _register(client)
    r = client.post(
        "/api/oauth/token",
        data={"grant_type": "password", "client_id": client_id},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "unsupported_grant_type"


def test_revoke_unknown_token(client):
    r = client.post("/api/oauth/revoke", data={"token": "inconnu"})
    assert r.status_code == 200


def test_revoke_token(client, db_session, bureau_member):
    client_id = _register(client)
    pair = oauth_store.issue_tokens(db_session, client_id, bureau_member.id)
    r = client.post("/api/oauth/revoke", data={"token": pair.access_token})
    assert r.status_code == 200
    assert oauth_store.member_for_access_token(db_session, pair.access_token) is None
