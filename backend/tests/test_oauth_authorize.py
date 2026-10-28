"""Authorize + consentement du serveur OAuth MCP."""
from __future__ import annotations

import base64
import hashlib
import re
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.models.models import Member
from app.services import oauth_store

REDIRECT = "http://localhost:33418/callback"
VERIFIER = "v" * 64


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


@pytest.fixture()
def anon(db_session):
    """Client sans override d'auth : la session web vient du cookie."""
    from app.core.deps import get_db
    from app.main import app

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, follow_redirects=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def oauth_client(db_session):
    return oauth_store.register_client(db_session, "Claude <Code>", [REDIRECT])


def _login(anon, member):
    anon.cookies.set("access_token", create_access_token(member.id))


def _params(oauth_client, **over):
    params = {
        "response_type": "code",
        "client_id": oauth_client.client_id,
        "redirect_uri": REDIRECT,
        "code_challenge": _challenge(VERIFIER),
        "code_challenge_method": "S256",
        "state": "xyz",
        "resource": "http://localhost:3000/api/mcp",
    }
    params.update(over)
    return {k: v for k, v in params.items() if v is not None}


def _consent_request(html: str) -> str:
    return re.search(r'name="request" value="([^"]+)"', html).group(1)


def test_authorize_unknown_client(anon, oauth_client, bureau_member):
    _login(anon, bureau_member)
    r = anon.get("/api/oauth/authorize", params=_params(oauth_client, client_id="nope"))
    assert r.status_code == 400


def test_authorize_unregistered_redirect(anon, oauth_client, bureau_member):
    _login(anon, bureau_member)
    r = anon.get(
        "/api/oauth/authorize",
        params=_params(oauth_client, redirect_uri="https://claude.ai/api/mcp/auth_callback"),
    )
    assert r.status_code == 400
    assert "location" not in r.headers


def test_authorize_plain_pkce(anon, oauth_client, bureau_member):
    _login(anon, bureau_member)
    r = anon.get(
        "/api/oauth/authorize", params=_params(oauth_client, code_challenge_method="plain")
    )
    assert r.status_code == 400


def test_authorize_wrong_resource(anon, oauth_client, bureau_member):
    _login(anon, bureau_member)
    r = anon.get(
        "/api/oauth/authorize", params=_params(oauth_client, resource="https://autre/api")
    )
    assert r.status_code == 400


def test_authorize_no_session_redirects_to_google(anon, oauth_client):
    r = anon.get("/api/oauth/authorize", params=_params(oauth_client))
    assert r.status_code == 303
    assert r.headers["location"].startswith(
        "/api/auth/google/login?next=%2Fapi%2Foauth%2Fauthorize"
    )


def test_authorize_staff_forbidden(anon, oauth_client, db_session):
    staff = Member(nom="S", prenom="Staff", email="staff@lateb.eu", roles=["staff"])
    db_session.add(staff)
    db_session.flush()
    _login(anon, staff)
    r = anon.get("/api/oauth/authorize", params=_params(oauth_client))
    assert r.status_code == 403
    assert "bureau" in r.text


def test_authorize_shows_consent(anon, oauth_client, bureau_member):
    _login(anon, bureau_member)
    r = anon.get("/api/oauth/authorize", params=_params(oauth_client))
    assert r.status_code == 200
    assert "Claude &lt;Code&gt;" in r.text  # échappé
    assert "bureau@lateb.eu" in r.text


def test_consent_allow_redirects_with_code(anon, oauth_client, bureau_member):
    _login(anon, bureau_member)
    page = anon.get("/api/oauth/authorize", params=_params(oauth_client))
    r = anon.post(
        "/api/oauth/authorize/consent",
        data={"request": _consent_request(page.text), "decision": "allow"},
    )
    assert r.status_code == 303
    loc = r.headers["location"]
    assert loc.startswith(REDIRECT)
    q = parse_qs(urlsplit(loc).query)
    assert q["state"] == ["xyz"]

    tok = anon.post(
        "/api/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": oauth_client.client_id,
            "code": q["code"][0],
            "redirect_uri": REDIRECT,
            "code_verifier": VERIFIER,
        },
    )
    assert tok.status_code == 200, tok.text


def test_consent_loopback_other_port(anon, oauth_client, bureau_member):
    _login(anon, bureau_member)
    other = "http://localhost:51000/callback"
    page = anon.get("/api/oauth/authorize", params=_params(oauth_client, redirect_uri=other))
    assert page.status_code == 200
    r = anon.post(
        "/api/oauth/authorize/consent",
        data={"request": _consent_request(page.text), "decision": "allow"},
    )
    assert r.headers["location"].startswith(other + "?code=")


def test_consent_deny(anon, oauth_client, bureau_member):
    _login(anon, bureau_member)
    page = anon.get("/api/oauth/authorize", params=_params(oauth_client))
    r = anon.post(
        "/api/oauth/authorize/consent",
        data={"request": _consent_request(page.text), "decision": "deny"},
    )
    assert r.status_code == 303
    q = parse_qs(urlsplit(r.headers["location"]).query)
    assert q["error"] == ["access_denied"]
    assert q["state"] == ["xyz"]


def test_consent_tampered(anon, oauth_client, bureau_member):
    _login(anon, bureau_member)
    page = anon.get("/api/oauth/authorize", params=_params(oauth_client))
    r = anon.post(
        "/api/oauth/authorize/consent",
        data={"request": _consent_request(page.text) + "x", "decision": "allow"},
    )
    assert r.status_code == 400


def test_consent_other_member(anon, oauth_client, bureau_member, db_session):
    _login(anon, bureau_member)
    page = anon.get("/api/oauth/authorize", params=_params(oauth_client))
    other = Member(nom="O", prenom="Autre", email="autre@lateb.eu", roles=["bureau"])
    db_session.add(other)
    db_session.flush()
    _login(anon, other)
    r = anon.post(
        "/api/oauth/authorize/consent",
        data={"request": _consent_request(page.text), "decision": "allow"},
    )
    assert r.status_code == 400
