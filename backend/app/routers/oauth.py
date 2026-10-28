"""Serveur d'autorisation OAuth 2.1 du MCP.

Découverte (RFC 9728 / RFC 8414), enregistrement dynamique (RFC 7591),
token et révocation. Clients publics uniquement, PKCE S256 obligatoire.
"""
from __future__ import annotations

import time
from html import escape
from typing import Optional
from urllib.parse import urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from ..config import settings
from ..core.deps import get_db
from ..core.security import decode_token
from ..models.models import Member
from ..services import oauth_store
from ..services.oauth_store import OAuthError

well_known_router = APIRouter(tags=["oauth"])
router = APIRouter(prefix="/api/oauth", tags=["oauth"])

GRANT_TYPES = ["authorization_code", "refresh_token"]


def _base() -> str:
    return settings.PUBLIC_BASE_URL.rstrip("/")


def mcp_resource() -> str:
    return f"{_base()}/api/mcp"


def _error(err: OAuthError, status_code: int = status.HTTP_400_BAD_REQUEST) -> JSONResponse:
    body = {"error": err.error}
    if err.description:
        body["error_description"] = err.description
    return JSONResponse(body, status_code=status_code, headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------------------
# Découverte
# ---------------------------------------------------------------------------


@well_known_router.get("/.well-known/oauth-protected-resource/api/mcp")
def protected_resource_metadata():
    return {
        "resource": mcp_resource(),
        "authorization_servers": [_base()],
        "bearer_methods_supported": ["header"],
    }


def _as_metadata() -> dict:
    base = _base()
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/api/oauth/authorize",
        "token_endpoint": f"{base}/api/oauth/token",
        "registration_endpoint": f"{base}/api/oauth/register",
        "revocation_endpoint": f"{base}/api/oauth/revoke",
        "response_types_supported": ["code"],
        "grant_types_supported": GRANT_TYPES,
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "revocation_endpoint_auth_methods_supported": ["none"],
    }


@well_known_router.get("/.well-known/oauth-authorization-server")
def authorization_server_metadata():
    return _as_metadata()


# Certains clients MCP ne cherchent que la découverte OIDC
@well_known_router.get("/.well-known/openid-configuration")
def openid_configuration():
    return _as_metadata()


# ---------------------------------------------------------------------------
# Enregistrement dynamique
# ---------------------------------------------------------------------------


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        return _error(OAuthError("invalid_client_metadata", "Corps JSON attendu"))
    redirect_uris = payload.get("redirect_uris")
    if not isinstance(redirect_uris, list):
        redirect_uris = []
    client_name = payload.get("client_name")
    try:
        client = oauth_store.register_client(
            db, client_name if isinstance(client_name, str) else None, redirect_uris
        )
    except OAuthError as err:
        return _error(err)
    db.commit()
    return JSONResponse(
        {
            "client_id": client.client_id,
            "client_name": client.client_name,
            "redirect_uris": client.redirect_uris,
            "token_endpoint_auth_method": "none",
            "grant_types": GRANT_TYPES,
            "response_types": ["code"],
            "client_id_issued_at": int(time.time()),
        },
        status_code=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------------
# Token / révocation
# ---------------------------------------------------------------------------


@router.post("/token")
def token(
    grant_type: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    code: Optional[str] = Form(None),
    redirect_uri: Optional[str] = Form(None),
    code_verifier: Optional[str] = Form(None),
    refresh_token: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    if grant_type not in GRANT_TYPES:
        return _error(OAuthError("unsupported_grant_type"))
    if oauth_store.get_client(db, client_id or "") is None:
        return _error(OAuthError("invalid_client", "client_id inconnu"), status.HTTP_400_BAD_REQUEST)
    try:
        if grant_type == "authorization_code":
            pair = oauth_store.exchange_code(
                db, client_id, code or "", redirect_uri or "", code_verifier or ""
            )
        else:
            pair = oauth_store.refresh_tokens(db, client_id, refresh_token or "")
    except OAuthError as err:
        # La révocation de famille sur réutilisation doit être persistée
        db.commit()
        return _error(err)
    db.commit()
    return JSONResponse(
        {
            "access_token": pair.access_token,
            "token_type": "Bearer",
            "expires_in": pair.expires_in,
            "refresh_token": pair.refresh_token,
        },
        headers={"Cache-Control": "no-store"},
    )


@router.post("/revoke")
def revoke(token: Optional[str] = Form(None), db: Session = Depends(get_db)):
    if token:
        oauth_store.revoke_token(db, token)
        db.commit()
    return JSONResponse({}, status_code=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Authorize + consentement
# ---------------------------------------------------------------------------

CONSENT_MAX_AGE = 600
_consent_signer = URLSafeTimedSerializer(settings.SECRET_KEY, salt="mcp-consent")


def _page(title: str, body: str, status_code: int = status.HTTP_200_OK) -> HTMLResponse:
    html = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
body{{font-family:system-ui,sans-serif;background:#f4f4f5;color:#18181b;margin:0;
display:flex;min-height:100vh;align-items:center;justify-content:center;padding:16px}}
main{{background:#fff;border-radius:12px;padding:28px;max-width:420px;width:100%;
box-shadow:0 1px 3px rgba(0,0,0,.1)}}
h1{{font-size:1.2rem;margin:0 0 12px}} p{{line-height:1.5}}
.actions{{display:flex;gap:8px;margin-top:20px}}
button{{flex:1;padding:10px;border-radius:8px;border:1px solid #d4d4d8;font-size:1rem;cursor:pointer;background:#fff}}
button.primary{{background:#18181b;color:#fff;border-color:#18181b}}
</style></head><body><main>{body}</main></body></html>"""
    return HTMLResponse(html, status_code=status_code, headers={"Cache-Control": "no-store"})


def _error_page(message: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> HTMLResponse:
    return _page("Autorisation impossible", f"<h1>Autorisation impossible</h1><p>{escape(message)}</p>", status_code)


def _with_query(uri: str, params: dict) -> str:
    parts = urlsplit(uri)
    extra = urlencode({k: v for k, v in params.items() if v is not None})
    query = f"{parts.query}&{extra}" if parts.query else extra
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def _session_member(request: Request, db: Session) -> Optional[Member]:
    raw = request.cookies.get("access_token")
    member_id = decode_token(raw, expected_type="access") if raw else None
    return db.get(Member, member_id) if member_id is not None else None


def _is_bureau(member: Member) -> bool:
    return bool(member.roles) and "bureau" in member.roles


@router.get("/authorize")
def authorize(
    request: Request,
    response_type: Optional[str] = None,
    client_id: Optional[str] = None,
    redirect_uri: Optional[str] = None,
    code_challenge: Optional[str] = None,
    code_challenge_method: Optional[str] = None,
    state: Optional[str] = None,
    resource: Optional[str] = None,
    db: Session = Depends(get_db),
):
    # Erreurs sur le client ou la redirect_uri : jamais de redirection (RFC 6749 §4.1.2.1)
    client = oauth_store.get_client(db, client_id or "")
    if client is None:
        return _error_page("Client inconnu.")
    if not redirect_uri or not oauth_store.redirect_uri_matches(client.redirect_uris, redirect_uri):
        return _error_page("redirect_uri non enregistrée pour ce client.")
    if response_type != "code":
        return _error_page("Seul response_type=code est supporté.")
    if code_challenge_method != "S256" or not code_challenge:
        return _error_page("PKCE S256 obligatoire.")
    if resource and resource.rstrip("/") != mcp_resource():
        return _error_page("Ressource inconnue.")

    member = _session_member(request, db)
    if member is None:
        target = request.url.path + ("?" + request.url.query if request.url.query else "")
        return RedirectResponse(
            "/api/auth/google/login?" + urlencode({"next": target}),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    if not _is_bureau(member):
        return _error_page("Accès MCP réservé au bureau.", status.HTTP_403_FORBIDDEN)

    signed = _consent_signer.dumps(
        {
            "client_id": client.client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "state": state,
            "resource": resource,
            "membre_id": member.id,
        }
    )
    name = client.client_name or "Une application"
    body = f"""<h1>Autoriser l'accès au planning ?</h1>
<p><strong>{escape(name)}</strong> veut accéder au planning du bar en ton nom
(<strong>{escape(member.email or "")}</strong>) : consulter et créer des événements.</p>
<p>Ne valide que si tu viens toi-même de lancer cette connexion.</p>
<form method="post" action="/api/oauth/authorize/consent">
<input type="hidden" name="request" value="{escape(signed)}">
<div class="actions">
<button type="submit" name="decision" value="deny">Refuser</button>
<button type="submit" name="decision" value="allow" class="primary">Autoriser</button>
</div></form>"""
    return _page("Autoriser l'accès", body)


@router.post("/authorize/consent")
def authorize_consent(
    request: Request,
    request_data: str = Form("", alias="request"),
    decision: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        data = _consent_signer.loads(request_data, max_age=CONSENT_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return _error_page("Demande expirée ou invalide, relance la connexion depuis ton agent.")

    # Le formulaire n'est valable que pour le membre connecté qui l'a affiché
    member = _session_member(request, db)
    if member is None or member.id != data.get("membre_id") or not _is_bureau(member):
        return _error_page("Session invalide, relance la connexion depuis ton agent.")
    client = oauth_store.get_client(db, data.get("client_id") or "")
    if client is None or not oauth_store.redirect_uri_matches(client.redirect_uris, data["redirect_uri"]):
        return _error_page("Client inconnu.")

    if decision != "allow":
        location = _with_query(data["redirect_uri"], {"error": "access_denied", "state": data.get("state")})
        return RedirectResponse(location, status_code=status.HTTP_303_SEE_OTHER)

    code = oauth_store.issue_code(
        db, client, member.id, data["redirect_uri"], data["code_challenge"], data.get("resource")
    )
    db.commit()
    location = _with_query(data["redirect_uri"], {"code": code, "state": data.get("state")})
    return RedirectResponse(location, status_code=status.HTTP_303_SEE_OTHER)
