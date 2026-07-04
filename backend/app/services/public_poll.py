"""Formulaire public de disponibilités : soumission sans auth + résolution bureau.

Réutilise la mécanique de l'import CSV (alias map, fuzzy matching, upsert des
availabilities avec delta de stats). Un nom non reconnu est conservé en
`PendingSubmission` jusqu'à résolution par le bureau.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..models.models import Event, Member, PendingSubmission, Slot
from .csv_import import (
    _build_alias_map,
    _fuzzy_candidates,
    _normalise,
    _save_alias_if_new,
    _save_availabilities,
)

# Plafond de soumissions en attente par événement (anti-abus minimal)
MAX_PENDING_PER_EVENT = 200


class PendingLimitError(Exception):
    """Trop de soumissions en attente sur cet événement."""


def is_open(event: Event) -> Tuple[bool, Optional[str]]:
    """Retourne (ouvert, raison_fermeture) — raison ∈ {"closed", "deadline"}."""
    if not event.inscriptions_ouvertes:
        return False, "closed"
    # Datetimes naïfs comme partout dans l'app : la deadline est comparée à
    # l'horloge du serveur, précision suffisante pour une clôture d'inscriptions.
    if event.inscriptions_deadline and datetime.now() > event.inscriptions_deadline:
        return False, "deadline"
    return True, None


def _validated_row_avails(
    db: Session, event_id: int, reponses: List[dict]
) -> Tuple[List[dict], Dict[int, int]]:
    """Valide les creneau_id contre les slots de l'event, dédoublonne (dernier
    gagne) et retourne (row_avails pour _save_availabilities, slot_id_to_hr)."""
    slots = db.query(Slot).filter(Slot.evenement_id == event_id).all()
    slot_id_to_hr = {s.id: s.heure_relative for s in slots}
    by_slot: Dict[int, str] = {}
    for r in reponses:
        creneau_id = r["creneau_id"]
        if creneau_id not in slot_id_to_hr:
            raise ValueError(f"creneau_id {creneau_id} inconnu pour cet événement")
        by_slot[creneau_id] = r["statut"]
    row_avails = [
        {"slot_id": slot_id, "statut": statut} for slot_id, statut in by_slot.items()
    ]
    return row_avails, slot_id_to_hr


def _delete_pending(db: Session, event_id: int, nom_normalise: str) -> None:
    db.query(PendingSubmission).filter(
        PendingSubmission.evenement_id == event_id,
        PendingSubmission.nom_normalise == nom_normalise,
    ).delete()


def submit(db: Session, event: Event, nom: str, reponses: List[dict]) -> str:
    """Enregistre une soumission publique. Retourne "matched" ou "pending".

    - Nom résolu (exact ou fuzzy ≥ seuil) : upsert des availabilities (une
      re-soumission écrase, les stats sont ajustées par delta) + alias appris.
    - Nom inconnu : upsert d'une PendingSubmission par (event, nom normalisé).
    """
    nom = nom.strip()
    nom_norm = _normalise(nom)
    row_avails, slot_id_to_hr = _validated_row_avails(db, event.id, reponses)

    alias_map = _build_alias_map(db)
    member_id = alias_map.get(nom_norm)
    if member_id is None:
        candidates = _fuzzy_candidates(
            nom, alias_map, settings.FUZZY_MATCH_THRESHOLD, limit=1
        )
        if candidates:
            member_id = candidates[0][0]

    if member_id is not None:
        _save_alias_if_new(db, nom, member_id)
        _save_availabilities(
            db, event.id, member_id, row_avails, slot_id_to_hr, event.type
        )
        # Une soumission précédente du même nom a pu rester en attente
        # (ex. membre/alias créé entre-temps) : elle est désormais couverte.
        _delete_pending(db, event.id, nom_norm)
        db.commit()
        return "matched"

    reponses_clean = [
        {"creneau_id": r["slot_id"], "statut": r["statut"]} for r in row_avails
    ]
    existing = (
        db.query(PendingSubmission)
        .filter(
            PendingSubmission.evenement_id == event.id,
            PendingSubmission.nom_normalise == nom_norm,
        )
        .first()
    )
    if existing:
        existing.nom_saisi = nom
        existing.reponses = reponses_clean
        existing.updated_at = datetime.now()
    else:
        count = (
            db.query(PendingSubmission)
            .filter(PendingSubmission.evenement_id == event.id)
            .count()
        )
        if count >= MAX_PENDING_PER_EVENT:
            raise PendingLimitError(
                "Trop de soumissions en attente pour cet événement"
            )
        db.add(
            PendingSubmission(
                evenement_id=event.id,
                nom_saisi=nom,
                nom_normalise=nom_norm,
                reponses=reponses_clean,
            )
        )
    try:
        db.commit()
    except IntegrityError:
        # Course entre deux soumissions simultanées du même nom : re-tente en update
        db.rollback()
        row = (
            db.query(PendingSubmission)
            .filter(
                PendingSubmission.evenement_id == event.id,
                PendingSubmission.nom_normalise == nom_norm,
            )
            .first()
        )
        if row:
            row.nom_saisi = nom
            row.reponses = reponses_clean
            row.updated_at = datetime.now()
            db.commit()
    return "pending"


def list_pending(db: Session, event_id: int) -> List[dict]:
    """Soumissions en attente + suggestions fuzzy, au shape de NameResolutionModal."""
    alias_map = _build_alias_map(db)
    result = []
    rows = (
        db.query(PendingSubmission)
        .filter(PendingSubmission.evenement_id == event_id)
        .order_by(PendingSubmission.created_at)
        .all()
    )
    for row in rows:
        candidates = _fuzzy_candidates(
            row.nom_saisi, alias_map, threshold=50, limit=5
        )
        members = {
            m.id: m for m in db.query(Member).filter(Member.id.in_([c[0] for c in candidates]))
        } if candidates else {}
        suggestions = [
            {
                "member_id": member_id,
                "display_name": f"{members[member_id].prenom} {members[member_id].nom}".strip(),
                "score": round(score, 1),
            }
            for member_id, _alias, score in candidates
            if member_id in members
        ]
        result.append(
            {
                "id": row.id,
                "csv_name": row.nom_saisi,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "suggestions": suggestions,
                "availabilities": row.reponses,
            }
        )
    return result


def resolve_pending_submissions(
    db: Session, event_id: int, resolutions: List[dict]
) -> int:
    """Miroir de csv_import.resolve_pending, mais par creneau_id.

    resolutions: [{csv_name, member_id?, create_new, availabilities: [{creneau_id, statut}]}]
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise ValueError(f"Event {event_id} not found")

    resolved = 0
    for entry in resolutions:
        csv_name = entry["csv_name"]
        row_avails, slot_id_to_hr = _validated_row_avails(
            db, event_id, entry.get("availabilities", [])
        )

        if entry.get("create_new"):
            parts = csv_name.rsplit(" ", 1)
            prenom = parts[0] if len(parts) > 1 else csv_name
            nom = parts[1] if len(parts) > 1 else ""
            member = Member(nom=nom, prenom=prenom, roles=["staff"])
            db.add(member)
            db.flush()
            member_id = member.id
        else:
            member_id = entry.get("member_id")
            if not member_id:
                continue

        _save_alias_if_new(db, csv_name, member_id)
        _save_availabilities(
            db, event_id, member_id, row_avails, slot_id_to_hr, event.type
        )
        _delete_pending(db, event_id, _normalise(csv_name))
        resolved += 1

    db.commit()
    return resolved
