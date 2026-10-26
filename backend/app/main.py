"""FastAPI application entry point."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .routers import auth, events, export, import_historique, members, public, saisons

app = FastAPI(title="S.A.L.O.P.E API", version="1.0.0", redirect_slashes=False)

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
app.include_router(import_historique.router)
app.include_router(public.router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
