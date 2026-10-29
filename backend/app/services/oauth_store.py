"""Serveur d'autorisation OAuth 2.1 du MCP : clients, codes PKCE, tokens.

Les codes et tokens sont opaques et stockés hashés (SHA-256) : un token MCP
n'est jamais un JWT de l'app web, et inversement. Toutes les fonctions font
`flush()` ; le commit revient à l'appelant.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlsplit

from sqlalchemy import exists
from sqlalchemy.orm import Session

from ..config import settings
from ..models.models import Member, OAuthAuthorizationCode, OAuthClient, OAuthToken

CODE_TTL = timedelta(minutes=5)
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
# DCR ouvert sans auth : on borne ce qu'un appel peut stocker
MAX_REDIRECT_URIS = 10
MAX_REDIRECT_URI_LENGTH = 2048
# Un client sans code ni token depuis ce délai est abandonné
ORPHAN_CLIENT_TTL = timedelta(days=1)


class OAuthError(Exception):
    def __init__(self, error: str, description: Optional[str] = None):
        super().__init__(description or error)
        self.error = error
        self.description = description


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


def _now() -> datetime:
    # UTC naïf (convention projet : datetimes sans timezone)
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_secret(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Redirect URIs
# ---------------------------------------------------------------------------


def _parse(uri: str):
    """urlsplit strict : None si userinfo (`user@host` déguise l'hôte réel),
    port invalide ou fragment."""
    try:
        parts = urlsplit(uri)
        parts.port  # lève ValueError si le port n'est pas numérique
    except (TypeError, ValueError):
        return None
    if "@" in parts.netloc or parts.fragment or not parts.hostname:
        return None
    return parts


def _loopback_key(uri: str) -> Optional[tuple[str, str, str, str]]:
    """(scheme, host, path, query) d'une URI loopback http, sans le port."""
    parts = _parse(uri)
    if parts is None or parts.scheme != "http" or parts.hostname not in _LOOPBACK_HOSTS:
        return None
    return parts.scheme, parts.hostname, parts.path or "/", parts.query


def redirect_uri_allowed(uri: str) -> bool:
    """URI acceptée à l'enregistrement : allowlist `MCP_ALLOWED_REDIRECT_URIS`."""
    parts = _parse(uri)
    if parts is None:
        return False
    for pattern in settings.MCP_ALLOWED_REDIRECT_URIS.split(","):
        pattern = pattern.strip()
        if not pattern:
            continue
        if pattern.endswith(":*"):
            # Loopback, port et chemin libres ; comparaison sur l'hôte réellement parsé
            p_scheme, p_host = pattern[:-2].split("://", 1)
            if parts.scheme == p_scheme and parts.hostname == p_host.strip("[]"):
                return True
        elif uri == pattern:
            return True
    return False


def redirect_uri_matches(registered: list[str], requested: str) -> bool:
    """Match exact, sauf le port des URIs loopback qui est libre (RFC 8252)."""
    if _parse(requested) is None:
        return False
    if requested in registered:
        return True
    key = _loopback_key(requested)
    return key is not None and any(_loopback_key(r) == key for r in registered)


# ---------------------------------------------------------------------------
# Clients (Dynamic Client Registration)
# ---------------------------------------------------------------------------


def register_client(
    db: Session, client_name: Optional[str], redirect_uris: list[str]
) -> OAuthClient:
    if not redirect_uris:
        raise OAuthError("invalid_redirect_uri", "Au moins une redirect_uri est requise")
    if len(redirect_uris) > MAX_REDIRECT_URIS:
        raise OAuthError(
            "invalid_redirect_uri", f"{MAX_REDIRECT_URIS} redirect_uris maximum"
        )
    for uri in redirect_uris:
        if (
            not isinstance(uri, str)
            or len(uri) > MAX_REDIRECT_URI_LENGTH
            or not redirect_uri_allowed(uri)
        ):
            raise OAuthError("invalid_redirect_uri", f"redirect_uri non autorisée : {uri}")
    client = OAuthClient(
        client_id=secrets.token_urlsafe(24),
        client_name=(client_name or "").strip()[:200] or None,
        redirect_uris=list(redirect_uris),
        created_at=_now(),
    )
    db.add(client)
    db.flush()
    return client


def purge_expired(db: Session) -> None:
    """Supprime codes et tokens expirés, puis les clients orphelins.

    Un refresh révoqué mais non expiré est conservé : il sert à détecter sa
    réutilisation (révocation de famille).
    """
    now = _now()
    db.query(OAuthAuthorizationCode).filter(
        OAuthAuthorizationCode.expires_at <= now
    ).delete(synchronize_session=False)
    db.query(OAuthToken).filter(OAuthToken.expires_at <= now).delete(
        synchronize_session=False
    )
    has_code = exists().where(OAuthAuthorizationCode.client_id == OAuthClient.client_id)
    has_token = exists().where(OAuthToken.client_id == OAuthClient.client_id)
    db.query(OAuthClient).filter(
        OAuthClient.created_at <= now - ORPHAN_CLIENT_TTL, ~has_code, ~has_token
    ).delete(synchronize_session=False)
    db.flush()


def get_client(db: Session, client_id: str) -> Optional[OAuthClient]:
    if not client_id:
        return None
    return db.get(OAuthClient, client_id)


# ---------------------------------------------------------------------------
# Codes d'autorisation (PKCE S256)
# ---------------------------------------------------------------------------


def _pkce_s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def issue_code(
    db: Session,
    client: OAuthClient,
    membre_id: int,
    redirect_uri: str,
    code_challenge: str,
    resource: Optional[str],
) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(
        OAuthAuthorizationCode(
            code_hash=hash_secret(raw),
            client_id=client.client_id,
            membre_id=membre_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            resource=resource,
            expires_at=_now() + CODE_TTL,
        )
    )
    db.flush()
    return raw


def exchange_code(
    db: Session, client_id: str, code: str, redirect_uri: str, code_verifier: str
) -> TokenPair:
    row = (
        db.query(OAuthAuthorizationCode)
        .filter(OAuthAuthorizationCode.code_hash == hash_secret(code or ""))
        .with_for_update()
        .first()
    )
    if (
        row is None
        or row.used_at is not None
        or row.expires_at <= _now()
        or row.client_id != client_id
        or row.redirect_uri != redirect_uri
        or not code_verifier
        or not hmac.compare_digest(_pkce_s256(code_verifier), row.code_challenge)
    ):
        raise OAuthError("invalid_grant", "Code d'autorisation invalide")
    row.used_at = _now()
    return issue_tokens(db, client_id, row.membre_id)


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


def issue_tokens(
    db: Session, client_id: str, membre_id: int, family_id: Optional[str] = None
) -> TokenPair:
    family_id = family_id or secrets.token_hex(16)
    now = _now()
    access = secrets.token_urlsafe(32)
    refresh = secrets.token_urlsafe(32)
    access_ttl = timedelta(minutes=settings.MCP_ACCESS_TOKEN_EXPIRE_MINUTES)
    for raw, kind, ttl in (
        (access, "access", access_ttl),
        (refresh, "refresh", timedelta(days=settings.MCP_REFRESH_TOKEN_EXPIRE_DAYS)),
    ):
        db.add(
            OAuthToken(
                token_hash=hash_secret(raw),
                type=kind,
                client_id=client_id,
                membre_id=membre_id,
                family_id=family_id,
                expires_at=now + ttl,
                created_at=now,
            )
        )
    db.flush()
    return TokenPair(access, refresh, int(access_ttl.total_seconds()))


def _revoke_family(db: Session, family_id: str) -> None:
    now = _now()
    db.query(OAuthToken).filter(
        OAuthToken.family_id == family_id, OAuthToken.revoked_at.is_(None)
    ).update({OAuthToken.revoked_at: now}, synchronize_session="fetch")
    db.flush()


def refresh_tokens(db: Session, client_id: str, refresh_token: str) -> TokenPair:
    row = (
        db.query(OAuthToken)
        .filter(OAuthToken.token_hash == hash_secret(refresh_token or ""))
        .with_for_update()
        .first()
    )
    if row is None or row.type != "refresh" or row.client_id != client_id:
        raise OAuthError("invalid_grant", "Refresh token invalide")
    if row.revoked_at is not None:
        # Refresh déjà consommé : vol probable, on coupe toute la famille
        _revoke_family(db, row.family_id)
        raise OAuthError("invalid_grant", "Refresh token déjà utilisé")
    if row.expires_at <= _now():
        raise OAuthError("invalid_grant", "Refresh token expiré")
    row.revoked_at = _now()
    return issue_tokens(db, client_id, row.membre_id, family_id=row.family_id)


def revoke_token(db: Session, raw: str) -> None:
    row = (
        db.query(OAuthToken)
        .filter(OAuthToken.token_hash == hash_secret(raw or ""))
        .first()
    )
    if row is not None:
        _revoke_family(db, row.family_id)


def member_for_access_token(db: Session, raw: str) -> Optional[Member]:
    """Membre porteur d'un access token valide. Le rôle n'est PAS vérifié ici."""
    if not raw:
        return None
    row = (
        db.query(OAuthToken)
        .filter(OAuthToken.token_hash == hash_secret(raw))
        .first()
    )
    if (
        row is None
        or row.type != "access"
        or row.revoked_at is not None
        or row.expires_at <= _now()
    ):
        return None
    return db.get(Member, row.membre_id)
