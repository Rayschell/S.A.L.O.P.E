"""Endpoints publics (sans authentification) du formulaire de disponibilités.

L'accès se fait par le token de partage de l'événement (non devinable),
comme un lien Strawpoll.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.deps import get_db
from ..models.models import Event, Slot
from ..schemas.schemas import (
    PublicPollInfo,
    PublicSubmissionIn,
    PublicSubmissionResult,
)
from ..services import public_poll

router = APIRouter(prefix="/api/public", tags=["public"])


def _get_event_by_token(db: Session, token: str) -> Event:
    event = db.query(Event).filter(Event.public_token == token).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Sondage introuvable")
    return event


@router.get("/polls/{token}", response_model=PublicPollInfo)
def get_poll(token: str, db: Session = Depends(get_db)):
    event = _get_event_by_token(db, token)
    ouvert, raison = public_poll.is_open(event)
    slots = (
        db.query(Slot)
        .filter(Slot.evenement_id == event.id)
        .order_by(Slot.heure_debut)
        .all()
    )
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
