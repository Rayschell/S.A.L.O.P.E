"""FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.routing import Route

from .config import settings
from .mcp.server import mcp_asgi_app, mcp_lifespan
from .routers import auth, events, export, import_historique, logos, members, oauth, public, saisons

# Logs applicatifs (loggers "app.*") sur stdout : uvicorn ne configure que les siens
_app_logger = logging.getLogger("app")
if not _app_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    _app_logger.addHandler(_handler)
    _app_logger.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp_lifespan(app):
        yield


app = FastAPI(
    title="S.A.L.O.P.E API", version="1.0.0", redirect_slashes=False, lifespan=lifespan
)

# CORS â€” restrict to configured origins in production
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cookie de session signé, uniquement pour le state/nonce du flow OIDC
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="oidc_session",
    max_age=600,
    same_site="lax",
    https_only=settings.COOKIE_SECURE,
    path="/api/auth",
)

app.include_router(auth.router)
app.include_router(members.router)
app.include_router(events.router)
app.include_router(saisons.router)
app.include_router(export.router)
app.include_router(logos.router)
app.include_router(import_historique.router)
app.include_router(public.router)
app.include_router(oauth.well_known_router)
app.include_router(oauth.router)
# Serveur MCP : servi exactement sur /api/mcp (pas de Mount, qui imposerait un slash final)
app.router.routes.append(
    Route("/api/mcp", endpoint=mcp_asgi_app, methods=["GET", "POST", "DELETE"])
)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
