"""Création d'événement et de créneaux, partagée par l'API REST et le MCP."""
from __future__ import annotations

import secrets
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from ..models.models import Event, EventStatutEnum, EventTypeEnum, Slot


class EventPublieError(Exception):
    """Les créneaux d'un événement publié sont verrouillés."""


def build_slot_ranges(
    jour: date, debut: time, fin: time, pas_minutes: int = 60
) -> list[tuple[datetime, datetime]]:
    """Découpe [jour+debut, jour+fin] en pas de `pas_minutes`.

    Même algo que `buildSlots` du formulaire web : fin ≤ début = minuit passé,
    dernier créneau tronqué à la fin.
    """
    start = datetime.combine(jour, debut)
    end = datetime.combine(jour, fin)
    if end <= start:
        end += timedelta(days=1)
    step = timedelta(minutes=pas_minutes)
    ranges = []
    t = start
    while t < end:
        nxt = t + step
        ranges.append((t, min(nxt, end)))
        t = nxt
    return ranges


def recompute_heures_relatives(db: Session, event_id: int) -> None:
    """heure_relative = index du créneau trié par heure_debut (0, 1, 2…)."""
    slots = (
        db.query(Slot)
        .filter(Slot.evenement_id == event_id)
        .order_by(Slot.heure_debut)
        .all()
    )
    for idx, slot in enumerate(slots):
        slot.heure_relative = idx


def new_event(db: Session, nom: str, date: datetime, type: EventTypeEnum) -> Event:
    event = Event(nom=nom, date=date, type=type, public_token=secrets.token_urlsafe(16))
    db.add(event)
    db.flush()
    return event


def add_slots(
    db: Session,
    event: Event,
    ranges: list[tuple[datetime, datetime]],
    max_personnes: int,
) -> list[Slot]:
    """Ajoute des créneaux ; les doublons exacts (même début/fin) sont ignorés."""
    if event.statut == EventStatutEnum.publie:
        raise EventPublieError("Événement publié : créneaux verrouillés")
    existing = {
        (s.heure_debut, s.heure_fin)
        for s in db.query(Slot).filter(Slot.evenement_id == event.id)
    }
    for debut, fin in ranges:
        if (debut, fin) in existing:
            continue
        existing.add((debut, fin))
        db.add(
            Slot(
                evenement_id=event.id,
                heure_debut=debut,
                heure_fin=fin,
                heure_relative=0,
                max_personnes=max_personnes,
            )
        )
    db.flush()
    recompute_heures_relatives(db, event.id)
    db.flush()
    return (
        db.query(Slot)
        .filter(Slot.evenement_id == event.id)
        .order_by(Slot.heure_debut)
        .all()
    )
