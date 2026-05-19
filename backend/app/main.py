"""FastAPI application entry point."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import auth, events, export, members

app = FastAPI(title="S.A.L.O.P.E API", version="1.0.0", redirect_slashes=False)

# CORS — restrict to configured origins in production
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(members.router)
app.include_router(events.router)
app.include_router(export.router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
