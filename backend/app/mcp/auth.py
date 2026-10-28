"""Middleware ASGI : bearer token MCP obligatoire + rôle bureau revérifié."""
from __future__ import annotations

import json
from typing import Optional

import anyio

from ..config import settings
from ..services import oauth_store
from . import context


def _metadata_url() -> str:
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/.well-known/oauth-protected-resource/api/mcp"


def _check_token(raw: str) -> tuple[int, Optional[int]]:
    """(statut HTTP, membre_id) pour un access token MCP."""
    with context.open_session() as db:
        member = oauth_store.member_for_access_token(db, raw)
        if member is None:
            return 401, None
        # Revérifié à chaque requête : un membre sorti du bureau perd l'accès aussitôt
        if not member.roles or "bureau" not in member.roles:
            return 403, None
        return 200, member.id


class BearerAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def _reject(self, send, status: int, error: str) -> None:
        challenge = f'Bearer error="{error}", resource_metadata="{_metadata_url()}"'
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"www-authenticate", challenge.encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": json.dumps({"error": error}).encode()})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        auth = headers.get(b"authorization", b"").decode()
        scheme, _, raw = auth.partition(" ")
        if scheme.lower() != "bearer" or not raw.strip():
            await self._reject(send, 401, "invalid_token")
            return

        # SQLAlchemy est synchrone : hors de la boucle async pour ne pas figer l'API
        status, membre_id = await anyio.to_thread.run_sync(_check_token, raw.strip())
        if status == 401:
            await self._reject(send, 401, "invalid_token")
            return
        if status == 403:
            await self._reject(send, 403, "insufficient_scope")
            return

        scope.setdefault("state", {})["membre_id"] = membre_id
        await self.app(scope, receive, send)
