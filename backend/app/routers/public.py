"""Endpoints publics (sans authentification) du formulaire de disponibilités.

L'accès se fait par le token de partage de l'événement (non devinable),
comme un lien Strawpoll.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from ..config import settings
from ..core.deps import get_db
from ..models.models import Event, Slot
from ..schemas.schemas import (
    PublicPollInfo,
    PublicSubmissionIn,
    PublicSubmissionResult,
)
from ..services import public_poll
from ..services.apercu import (
    COULEUR_LATEB,
    TEXTES_GENERIQUES,
    date_courte,
    page_apercu_html,
    textes_apercu,
)
from ..services.apercu_img import rendre_apercu_png
from ..services.export_img import LATEB_THEME, _heure
from ..services.logo_theme import hex_color, logo_et_theme

router = APIRouter(prefix="/api/public", tags=["public"])


def _get_event_by_token(db: Session, token: str) -> Event:
    event = db.query(Event).filter(Event.public_token == token).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Sondage introuvable")
    return event


def _slots_tries(db: Session, event: Event) -> list[Slot]:
    return (
        db.query(Slot)
        .filter(Slot.evenement_id == event.id)
        .order_by(Slot.heure_debut)
        .all()
    )


@router.get("/polls/{token}", response_model=PublicPollInfo)
def get_poll(token: str, db: Session = Depends(get_db)):
    event = _get_event_by_token(db, token)
    ouvert, raison = public_poll.is_open(event)
    slots = _slots_tries(db, event)
    return PublicPollInfo(
        event_nom=event.nom,
        event_date=event.date,
        event_type=event.type,
        ouvert=ouvert,
        raison_fermeture=raison,
        slots=slots,
    )


@router.post("/polls/{token}", response_model=PublicSubmissionResult)
def submit_poll(
    token: str,
    payload: PublicSubmissionIn,
    db: Session = Depends(get_db),
):
    event = _get_event_by_token(db, token)
    ouvert, raison = public_poll.is_open(event)
    if not ouvert:
        if raison == "deadline":
            raise HTTPException(status_code=410, detail="Inscriptions clôturées")
        raise HTTPException(status_code=403, detail="Inscriptions fermées")

    reponses = [
        {"creneau_id": r.creneau_id, "statut": r.statut.value}
        for r in payload.reponses
    ]
    try:
        status = public_poll.submit(db, event, payload.nom, reponses)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except public_poll.PendingLimitError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return PublicSubmissionResult(status=status)


# ---------------------------------------------------------------------------
# Aperçu Open Graph (carte Discord / WhatsApp…) — servi aux robots par nginx
# ---------------------------------------------------------------------------

_CACHE_IMAGE = {"Cache-Control": "public, max-age=3600"}


@router.get("/polls/{token}/apercu", response_class=HTMLResponse)
def apercu_poll(token: str, db: Session = Depends(get_db)):
    """Page HTML portant les balises Open Graph du lien /dispo/{token}.

    Token inconnu → carte générique LATEB (200), pour ne rien laisser fuiter
    et ne pas afficher d'erreur dans Discord.
    """
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    event = db.query(Event).filter(Event.public_token == token).first()
    if event is None:
        titre, description = TEXTES_GENERIQUES
        url, image_url, couleur = f"{base}/", f"{base}/api/public/apercu.png", COULEUR_LATEB
    else:
        titre, description = textes_apercu(event, _slots_tries(db, event))
        _, theme = logo_et_theme(db, event)
        url = f"{base}/dispo/{token}"
        image_url = f"{base}/api/public/polls/{token}/apercu.png"
        couleur = hex_color((theme or LATEB_THEME)["frame"])
    return HTMLResponse(
        page_apercu_html(titre, description, url, image_url, couleur),
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/polls/{token}/apercu.png")
def apercu_poll_png(token: str, db: Session = Depends(get_db)):
    event = _get_event_by_token(db, token)
    slots = _slots_tries(db, event)
    if slots:
        debut, fin = slots[0].heure_debut, slots[-1].heure_fin
        ligne_date = f"{date_courte(debut)}\n{_heure(debut)} → {_heure(fin)}"
    else:
        ligne_date = date_courte(event.date)
    logo_png, theme = logo_et_theme(db, event)
    png = rendre_apercu_png(event.nom, ligne_date, logo_png, theme)
    return Response(content=png, media_type="image/png", headers=_CACHE_IMAGE)


@router.get("/apercu.png")
def apercu_generique_png():
    png = rendre_apercu_png(None, None, None, None)
    return Response(content=png, media_type="image/png", headers=_CACHE_IMAGE)
