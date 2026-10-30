"""Tools MCP du noyau V1, en fonctions pures sur une session SQLAlchemy."""
from __future__ import annotations

from datetime import date as date_cls, datetime, time
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..models.models import Event, EventStatutEnum, EventTypeEnum, Saison, Slot
from ..services.event_creation import add_slots, build_slot_ranges, new_event


def _parse_date(value: str, champ: str) -> date_cls:
    try:
        return date_cls.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"{champ} invalide (attendu AAAA-MM-JJ) : {value!r}")


def _parse_heure(value: str, champ: str) -> time:
    try:
        return time.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"{champ} invalide (attendu HH:MM) : {value!r}")


def _enum(enum_cls, value: Optional[str], champ: str):
    if value is None:
        return None
    try:
        return enum_cls(value)
    except ValueError:
        choix = ", ".join(e.value for e in enum_cls)
        raise ValueError(f"{champ} invalide : {value!r} (choix : {choix})")


def _slot_dict(s: Slot) -> dict:
    return {
        "id": s.id,
        "heure_debut": s.heure_debut.isoformat(),
        "heure_fin": s.heure_fin.isoformat(),
        "heure_relative": s.heure_relative,
        "max_personnes": s.max_personnes,
    }


def _event_dict(e: Event) -> dict:
    return {
        "id": e.id,
        "nom": e.nom,
        "type": e.type.value,
        "date": e.date.isoformat(),
        "statut": e.statut.value,
    }


def _event_url(event_id: int) -> str:
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/events/{event_id}"


def create_event(
    db: Session,
    nom: str,
    type: str,
    date: str,
    heure_debut: str,
    heure_fin: str,
    max_personnes: int = 3,
    duree_creneau_minutes: int = 60,
) -> dict:
    nom = (nom or "").strip()
    if not nom:
        raise ValueError("Le nom de l'événement est obligatoire")
    type_ = _enum(EventTypeEnum, type, "type")
    jour = _parse_date(date, "date")
    debut = _parse_heure(heure_debut, "heure_debut")
    fin = _parse_heure(heure_fin, "heure_fin")
    if not 1 <= max_personnes <= 99:
        raise ValueError("max_personnes doit être entre 1 et 99")
    if not 15 <= duree_creneau_minutes <= 240:
        raise ValueError("duree_creneau_minutes doit être entre 15 et 240")
    ranges = build_slot_ranges(jour, debut, fin, duree_creneau_minutes)
    if len(ranges) > 100:
        raise ValueError("Trop de créneaux (100 max)")

    # Heure locale naïve, comme les créneaux (convention projet)
    event = new_event(db, nom, datetime.combine(jour, debut), type_)
    slots = add_slots(db, event, ranges, max_personnes)
    db.commit()
    return {
        "event": _event_dict(event),
        "creneaux": [_slot_dict(s) for s in slots],
        "url": _event_url(event.id),
    }


def list_events(
    db: Session,
    statut: Optional[str] = None,
    type: Optional[str] = None,
    depuis: Optional[str] = None,
    jusqu_a: Optional[str] = None,
    limite: int = 20,
) -> list[dict]:
    nb_creneaux = (
        db.query(Slot.evenement_id, func.count(Slot.id).label("n"))
        .group_by(Slot.evenement_id)
        .subquery()
    )
    q = db.query(Event, func.coalesce(nb_creneaux.c.n, 0)).outerjoin(
        nb_creneaux, nb_creneaux.c.evenement_id == Event.id
    )
    statut_ = _enum(EventStatutEnum, statut, "statut")
    if statut_ is not None:
        q = q.filter(Event.statut == statut_)
    type_ = _enum(EventTypeEnum, type, "type")
    if type_ is not None:
        q = q.filter(Event.type == type_)
    if depuis:
        q = q.filter(Event.date >= datetime.combine(_parse_date(depuis, "depuis"), time.min))
    if jusqu_a:
        q = q.filter(Event.date <= datetime.combine(_parse_date(jusqu_a, "jusqu_a"), time.max))
    limite = max(1, min(limite, 100))
    rows = q.order_by(Event.date.desc()).limit(limite).all()
    return [{**_event_dict(e), "nb_creneaux": n} for e, n in rows]


def get_event(db: Session, event_id: int) -> dict:
    event = db.get(Event, event_id)
    if event is None:
        raise ValueError("Événement introuvable")
    slots = (
        db.query(Slot)
        .filter(Slot.evenement_id == event.id)
        .order_by(Slot.heure_debut)
        .all()
    )
    return {
        **_event_dict(event),
        "url": _event_url(event.id),
        "inscriptions_ouvertes": event.inscriptions_ouvertes,
        "inscriptions_deadline": (
            event.inscriptions_deadline.isoformat() if event.inscriptions_deadline else None
        ),
        "creneaux": [_slot_dict(s) for s in slots],
    }


def list_saisons(db: Session) -> list[dict]:
    saisons = db.query(Saison).order_by(Saison.date_debut.desc()).all()
    return [
        {
            "id": s.id,
            "nom": s.nom,
            "date_debut": s.date_debut.isoformat(),
            "date_fin": s.date_fin.isoformat() if s.date_fin else None,
        }
        for s in saisons
    ]
