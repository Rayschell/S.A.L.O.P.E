"""CSV import service: parses Strawpoll exports, resolves member names."""
from __future__ import annotations

import io
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session

from ..config import settings
from ..models.models import (
    Availability,
    AvailabilityStatusEnum,
    Event,
    EventTypeEnum,
    Member,
    MemberAlias,
    Slot,
    StatsMemberHeureRelative,
)

# Strawpoll CSV metadata columns (before the availability columns)
_META_COLS = 5  # #, Date(UTC), Name, UniqueCode, Country

_SLOT_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})\s+\((\d{2}:\d{2})\s+-\s+(\d{2}:\d{2})\)$"
)


def _parse_slot_header(header: str) -> Optional[Tuple[datetime, datetime]]:
    m = _SLOT_RE.match(header.strip())
    if not m:
        return None
    date_str, start_str, end_str = m.groups()
    fmt = "%Y-%m-%d %H:%M"
    start = datetime.strptime(f"{date_str} {start_str}", fmt)
    end = datetime.strptime(f"{date_str} {end_str}", fmt)
    if end <= start:  # slot crossing midnight (e.g. 23:00 - 00:00)
        end += timedelta(days=1)
    return start, end


def _normalise(s: str) -> str:
    return s.strip().lower()


def _build_alias_map(db: Session) -> Dict[str, int]:
    """Return {alias_lower: member_id} for all known aliases + member names."""
    alias_map: Dict[str, int] = {}
    for alias in db.query(MemberAlias).all():
        alias_map[_normalise(alias.valeur)] = alias.membre_id
    for member in db.query(Member).all():
        full = f"{member.prenom} {member.nom}"
        alias_map[_normalise(full)] = member.id
        alias_map[_normalise(member.nom)] = member.id
    return alias_map


def _fuzzy_candidates(
    name: str,
    alias_map: Dict[str, int],
    threshold: int,
    limit: int = 5,
) -> List[Tuple[int, str, float]]:
    """Return [(member_id, matched_alias, score), ...] sorted by score desc."""
    if not alias_map:
        return []
    results = process.extract(
        _normalise(name),
        list(alias_map.keys()),
        scorer=fuzz.WRatio,
        limit=limit,
    )
    seen_members: Dict[int, Tuple[int, str, float]] = {}
    for matched_alias, score, _ in results:
        if score < threshold:
            continue
        mid = alias_map[matched_alias]
        if mid not in seen_members or seen_members[mid][2] < score:
            seen_members[mid] = (mid, matched_alias, float(score))
    return sorted(seen_members.values(), key=lambda x: x[2], reverse=True)


def import_csv(
    db: Session,
    event_id: int,
    csv_bytes: bytes,
) -> dict:
    """
    Parse Strawpoll CSV, create slots, resolve names, save availabilities.
    Also increments fois_disponible for each yes/maybe availability.
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise ValueError(f"Event {event_id} not found")
    event_type = event.type
    text = csv_bytes.decode("utf-8-sig")
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]

    slot_cols = list(df.columns[_META_COLS:])
    if not slot_cols:
        raise ValueError("CSV contains no slot columns")

    # ------------------------------------------------------------------
    # 1. Ensure slots exist for this event (create if absent)
    # ------------------------------------------------------------------
    slot_label_to_id: Dict[str, int] = {}
    for label in slot_cols:
        parsed = _parse_slot_header(label)
        if not parsed:
            continue
        hd, hf = parsed
        slot = (
            db.query(Slot)
            .filter(
                Slot.evenement_id == event_id,
                Slot.heure_debut == hd,
                Slot.heure_fin == hf,
            )
            .first()
        )
        if not slot:
            slot = Slot(evenement_id=event_id, heure_debut=hd, heure_fin=hf)
            db.add(slot)
            db.flush()
        slot_label_to_id[label] = slot.id

    # Recompute heure_relative for all slots of this event
    all_event_slots = sorted(
        db.query(Slot).filter(Slot.evenement_id == event_id).all(),
        key=lambda s: s.heure_debut,
    )
    for hr_idx, ev_slot in enumerate(all_event_slots):
        ev_slot.heure_relative = hr_idx
    db.flush()

    # Build slot_id -> heure_relative map
    slot_id_to_hr: Dict[int, int] = {s.id: s.heure_relative for s in all_event_slots}

    # ------------------------------------------------------------------
    # 2. Resolve names
    # ------------------------------------------------------------------
    alias_map = _build_alias_map(db)
    threshold = settings.FUZZY_MATCH_THRESHOLD

    imported_count = 0
    pending = []

    for _, row in df.iterrows():
        csv_name: str = str(row.iloc[2]).strip()
        if not csv_name or csv_name == "-":
            continue

        # Build availability data for this row
        row_avails = []
        for label in slot_cols:
            if label not in slot_label_to_id:
                continue
            raw = str(row.get(label, "no")).strip().lower()
            if raw not in ("yes", "no", "maybe"):
                raw = "no"
            row_avails.append({"slot_id": slot_label_to_id[label], "statut": raw, "slot_label": label})

        # Exact match
        norm = _normalise(csv_name)
        if norm in alias_map:
            member_id = alias_map[norm]
            _save_alias_if_new(db, csv_name, member_id)
            _save_availabilities(db, event_id, member_id, row_avails, slot_id_to_hr, event_type)
            imported_count += 1
            continue

        # Fuzzy match
        candidates = _fuzzy_candidates(csv_name, alias_map, threshold)
        if candidates and candidates[0][2] >= threshold:
            member_id = candidates[0][0]
            _save_alias_if_new(db, csv_name, member_id)
            _save_availabilities(db, event_id, member_id, row_avails, slot_id_to_hr, event_type)
            imported_count += 1
            alias_map[norm] = member_id
        else:
            # Return to frontend for manual resolution
            suggestions = []
            for mid, matched_alias, score in candidates[:5]:
                m = db.query(Member).filter(Member.id == mid).first()
                if m:
                    suggestions.append(
                        {
                            "member_id": mid,
                            "display_name": f"{m.prenom} {m.nom}",
                            "score": round(score, 1),
                        }
                    )
            pending.append(
                {
                    "csv_name": csv_name,
                    "suggestions": suggestions,
                    "availabilities": [
                        {"slot_label": a["slot_label"], "statut": a["statut"]}
                        for a in row_avails
                    ],
                }
            )

    db.commit()
    return {"imported_count": imported_count, "pending": pending}


def resolve_pending(
    db: Session,
    event_id: int,
    resolutions: list,
    slot_label_to_id: Dict[str, int],
) -> int:
    """
    Apply manual name resolutions returned from the frontend.

    resolutions: list of {csv_name, member_id?, create_new, availabilities}
    Returns count of newly imported rows.
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise ValueError(f"Event {event_id} not found")
    event_type = event.type

    all_event_slots = db.query(Slot).filter(Slot.evenement_id == event_id).all()
    slot_id_to_hr: Dict[int, int] = {s.id: s.heure_relative for s in all_event_slots}

    imported = 0
    for entry in resolutions:
        csv_name = entry["csv_name"]
        raw_avails = entry.get("availabilities", [])
        row_avails = [
            {
                "slot_id": slot_label_to_id.get(a["slot_label"]),
                "statut": a["statut"],
                "slot_label": a["slot_label"],
            }
            for a in raw_avails
            if slot_label_to_id.get(a["slot_label"])
        ]

        if entry.get("create_new"):
            # Create a stub member
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
        _save_availabilities(db, event_id, member_id, row_avails, slot_id_to_hr, event_type)
        imported += 1

    db.commit()
    return imported


def _save_alias_if_new(db: Session, csv_name: str, member_id: int) -> None:
    exists = (
        db.query(MemberAlias)
        .filter(MemberAlias.valeur == csv_name.strip())
        .first()
    )
    if not exists:
        db.add(MemberAlias(membre_id=member_id, valeur=csv_name.strip()))
        db.flush()


def _save_availabilities(
    db: Session,
    event_id: int,
    member_id: int,
    row_avails: list,
    slot_id_to_hr: dict,
    event_type,
) -> None:
    for item in row_avails:
        slot_id = item["slot_id"]
        if not slot_id:
            continue
        statut_str = item["statut"]
        existing = (
            db.query(Availability)
            .filter(
                Availability.evenement_id == event_id,
                Availability.membre_id == member_id,
                Availability.creneau_id == slot_id,
            )
            .first()
        )
        if existing:
            existing.statut = AvailabilityStatusEnum(statut_str)
        else:
            db.add(
                Availability(
                    evenement_id=event_id,
                    membre_id=member_id,
                    creneau_id=slot_id,
                    statut=AvailabilityStatusEnum(statut_str),
                )
            )
        # Increment fois_disponible for yes/maybe
        if statut_str in ("yes", "maybe"):
            hr = slot_id_to_hr.get(slot_id)
            if hr is not None:
                stat = (
                    db.query(StatsMemberHeureRelative)
                    .filter_by(
                        membre_id=member_id,
                        type_evenement=event_type,
                        heure_relative=hr,
                    )
                    .first()
                )
                if stat:
                    stat.fois_disponible += 1
                else:
                    db.add(StatsMemberHeureRelative(
                        membre_id=member_id,
                        type_evenement=event_type,
                        heure_relative=hr,
                        fois_disponible=1,
                        fois_staffe=0,
                    ))


def get_slot_label_map(db: Session, event_id: int) -> Dict[str, int]:
    """Return {slot_label: slot_id} for an event's slots."""
    result = {}
    for slot in db.query(Slot).filter(Slot.evenement_id == event_id).all():
        hd = slot.heure_debut
        hf = slot.heure_fin
        label = f"{hd.strftime('%Y-%m-%d')} ({hd.strftime('%H:%M')} - {hf.strftime('%H:%M')})"
        result[label] = slot.id
    return result
