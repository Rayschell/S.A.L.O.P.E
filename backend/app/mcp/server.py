"""Serveur MCP (SDK officiel 2.x, streamable HTTP stateless, réponses JSON)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Callable, Optional

import anyio
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import ToolAnnotations

from . import context, tools
from .auth import BearerAuthMiddleware

mcp = MCPServer(
    "planning",
    version="1.0.0",
    instructions=(
        "Planning des staffs du bar LATEB. Les heures sont en heure locale "
        "(Europe/Paris). Un créneau dure une heure par défaut."
    ),
)

_LECTURE = ToolAnnotations(readOnlyHint=True, destructiveHint=False)


async def _run(fn: Callable[..., Any], *args) -> Any:
    """Exécute un tool (SQLAlchemy synchrone) dans un thread, hors de la boucle async."""

    def _call():
        with context.open_session() as db:
            return fn(db, *args)

    try:
        return await anyio.to_thread.run_sync(_call)
    except ValueError as exc:
        # Erreur d'usage (entrée invalide, event introuvable) : renvoyée au modèle en isError
        raise ToolError(str(exc)) from exc


@mcp.tool(
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)
)
async def create_event(
    nom: str,
    type: str,
    date: str,
    heure_debut: str,
    heure_fin: str,
    max_personnes: int = 3,
    duree_creneau_minutes: int = 60,
) -> dict:
    """Crée un événement en brouillon et ses créneaux, puis s'arrête.

    N'ouvre pas le formulaire de disponibilités et ne génère pas de planning.

    - type : "afterwork" ou "soiree"
    - date : AAAA-MM-JJ ; heure_debut / heure_fin : HH:MM (heure locale).
      Une fin inférieure ou égale au début signifie le lendemain (ex. 22:00 → 02:00).
    - max_personnes : capacité de chaque créneau (défaut 3)

    Exemple : « afterwork jeudi de 18h à 20h » →
    create_event(nom="Afterwork", type="afterwork", date="2026-11-05",
                 heure_debut="18:00", heure_fin="20:00") → 2 créneaux d'une heure.
    """
    return await _run(
        tools.create_event, nom, type, date, heure_debut, heure_fin, max_personnes, duree_creneau_minutes
    )


@mcp.tool(annotations=_LECTURE)
async def list_events(
    statut: Optional[str] = None,
    type: Optional[str] = None,
    depuis: Optional[str] = None,
    jusqu_a: Optional[str] = None,
    limite: int = 20,
) -> list[dict]:
    """Liste les événements, du plus récent au plus ancien.

    Filtres optionnels : statut ("brouillon" | "publie"), type ("afterwork" | "soiree"),
    depuis / jusqu_a (AAAA-MM-JJ, inclus). Exemple : list_events(statut="brouillon").
    """
    return await _run(tools.list_events, statut, type, depuis, jusqu_a, limite)


@mcp.tool(annotations=_LECTURE)
async def get_event(event_id: int) -> dict:
    """Détail d'un événement : créneaux et état du formulaire de disponibilités.

    Exemple : get_event(event_id=21).
    """
    return await _run(tools.get_event, event_id)


@mcp.tool(annotations=_LECTURE)
async def list_saisons() -> list[dict]:
    """Liste les saisons (mandats de bureau). date_fin null = saison en cours."""
    return await _run(tools.list_saisons)


class _McpEndpoint:
    """Délègue au session manager de la lifespan en cours."""

    manager: Optional[StreamableHTTPSessionManager] = None

    async def __call__(self, scope, receive, send):
        if self.manager is None:
            raise RuntimeError("Serveur MCP non démarré (lifespan)")
        await self.manager.handle_request(scope, receive, send)


_endpoint = _McpEndpoint()
mcp_asgi_app = BearerAuthMiddleware(_endpoint)


@asynccontextmanager
async def mcp_lifespan(app):
    # Un session manager ne peut tourner qu'une fois : on en recrée un à chaque
    # démarrage (les tests rejouent la lifespan à chaque TestClient).
    manager = StreamableHTTPSessionManager(
        app=mcp._lowlevel_server, json_response=True, stateless=True
    )
    async with manager.run():
        _endpoint.manager = manager
        try:
            yield
        finally:
            _endpoint.manager = None
