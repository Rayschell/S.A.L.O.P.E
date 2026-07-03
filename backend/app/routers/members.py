"""Members CRUD router."""
from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.deps import get_db, get_current_member, require_bureau
from ..core.security import hash_password
from ..models.models import (
    AffinityConstraint, Assignment, Availability, AvailabilityStatusEnum,
    Event, EventStatutEnum, EventTypeEnum,
    Member, MemberAlias, ResponsableBar, Saison, Slot, StatsMemberHeureRelative,
)
from ..schemas.schemas import (
    AliasCreate, AliasRead, MemberCreate, MemberOverviewItem, MemberRead, MemberReadFull,
    MemberStatsRead, MemberStatsEntry, MemberUpdate, MergeRequest,
    TimelineEvent, TimelineSlot, BIEN_MEMBRE_SEUIL_HEURES,
)

router = APIRouter(prefix="/api/members", tags=["members"])


def _saison_bounds(db: Session, saison_id: int) -> Tuple[datetime, datetime]:
    """Bornes datetime [debut, fin+1j) pour filtrer Event.date (fin incluse).

    date_fin NULL = saison en cours : borne haute ouverte (datetime.max).
    """
    saison = db.query(Saison).filter(Saison.id == saison_id).first()
    if not saison:
        raise HTTPException(status_code=404, detail="Saison introuvable")
    d0 = datetime.combine(saison.date_debut, time.min)
    if saison.date_fin is None:
        return d0, datetime.max
    d1 = datetime.combine(saison.date_fin, time.min) + timedelta(days=1)
    return d0, d1


@router.get("", response_model=List[MemberRead])
def list_members(
    db: Session = Depends(get_db),
    _: Member = Depends(get_current_member),
):
    return db.query(Member).order_by(Member.nom, Member.prenom).all()


@router.get("/stats-overview", response_model=List[MemberOverviewItem])
def get_stats_overview(
    saison_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    from collections import defaultdict
    members = db.query(Member).order_by(Member.nom, Member.prenom).all()

    query = (
        db.query(Assignment.membre_id, Event.type)
        .join(Slot, Assignment.creneau_id == Slot.id)
        .join(Event, Slot.evenement_id == Event.id)
        .filter(Event.statut == EventStatutEnum.publie)
    )
    if saison_id is not None:
        d0, d1 = _saison_bounds(db, saison_id)
        query = query.filter(Event.date >= d0, Event.date < d1)
    rows = query.all()

    # Convention du système : 1 créneau = 1 heure (stats heure_relative, quotas solveur)
    hours: dict = defaultdict(lambda: {"afterwork": 0.0, "soiree": 0.0})
    for membre_id, event_type in rows:
        if event_type == EventTypeEnum.afterwork:
            hours[membre_id]["afterwork"] += 1
        else:
            hours[membre_id]["soiree"] += 1

    result = []
    for m in members:
        h = hours[m.id]
        total = h["afterwork"] + h["soiree"]
        result.append(MemberOverviewItem(
            id=m.id,
            nom=m.nom,
            prenom=m.prenom,
            roles=m.roles,
            heures_afterwork=round(h["afterwork"], 1),
            heures_soiree=round(h["soiree"], 1),
            heures_total=round(total, 1),
            shifts_respo_bar_cumules=m.shifts_respo_bar_cumules,
            bien_membre=total >= BIEN_MEMBRE_SEUIL_HEURES,
        ))
    return result


@router.get("/{member_id}", response_model=MemberReadFull)
def get_member(
    member_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(get_current_member),
):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    return member


@router.post("", response_model=MemberRead, status_code=status.HTTP_201_CREATED)
def create_member(
    payload: MemberCreate,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    if payload.email:
        existing = db.query(Member).filter(Member.email == payload.email).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    member = Member(
        nom=payload.nom,
        prenom=payload.prenom,
        email=payload.email,
        roles=payload.roles,
        shifts_respo_bar_cumules=payload.shifts_respo_bar_cumules,
        hashed_password=hash_password(payload.password) if payload.password else None,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.put("/{member_id}", response_model=MemberRead)
def update_member(
    member_id: int,
    payload: MemberUpdate,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if payload.nom is not None:
        member.nom = payload.nom
    if payload.prenom is not None:
        member.prenom = payload.prenom
    if payload.email is not None:
        member.email = payload.email
    if payload.roles is not None:
        member.roles = payload.roles
    if payload.shifts_respo_bar_cumules is not None:
        member.shifts_respo_bar_cumules = payload.shifts_respo_bar_cumules
    if payload.password is not None:
        member.hashed_password = hash_password(payload.password)
    db.commit()
    db.refresh(member)
    return member


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(
    member_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    db.delete(member)
    db.commit()


@router.post("/{member_id}/aliases", response_model=AliasRead, status_code=status.HTTP_201_CREATED)
def add_alias(
    member_id: int,
    body: AliasCreate,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    valeur = body.valeur.strip()
    if not valeur:
        raise HTTPException(status_code=400, detail="Alias vide")
    existing = db.query(MemberAlias).filter(MemberAlias.valeur == valeur).first()
    if existing:
        other = db.query(Member).filter(Member.id == existing.membre_id).first()
        raise HTTPException(
            status_code=409,
            detail=f"Alias déjà utilisé par {other.prenom} {other.nom}" if other else "Alias déjà utilisé",
        )
    alias = MemberAlias(membre_id=member_id, valeur=valeur)
    db.add(alias)
    db.commit()
    db.refresh(alias)
    return alias


@router.delete("/{member_id}/aliases/{alias_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alias(
    member_id: int,
    alias_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    alias = (
        db.query(MemberAlias)
        .filter(MemberAlias.id == alias_id, MemberAlias.membre_id == member_id)
        .first()
    )
    if not alias:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alias not found")
    db.delete(alias)
    db.commit()


@router.post("/{member_id}/merge", response_model=MemberRead)
def merge_member(
    member_id: int,
    body: MergeRequest,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    """Fusionne un doublon (`source_member_id`) dans le membre `member_id` :
    réattribue dispos, affectations, stats, respos, affinités et alias, puis
    supprime le doublon. Les conflits (même créneau des deux côtés) gardent
    la donnée du membre cible."""
    target = db.query(Member).filter(Member.id == member_id).first()
    source = db.query(Member).filter(Member.id == body.source_member_id).first()
    if not target or not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if target.id == source.id:
        raise HTTPException(status_code=400, detail="Impossible de fusionner un membre avec lui-même")

    # Availabilities (unique : event × membre × créneau)
    target_avail_keys = {
        (a.evenement_id, a.creneau_id)
        for a in db.query(Availability).filter(Availability.membre_id == target.id)
    }
    for a in db.query(Availability).filter(Availability.membre_id == source.id).all():
        if (a.evenement_id, a.creneau_id) in target_avail_keys:
            db.delete(a)
        else:
            a.membre_id = target.id

    # Assignments (unique : créneau × membre)
    target_asgn_slots = {
        a.creneau_id for a in db.query(Assignment).filter(Assignment.membre_id == target.id)
    }
    for a in db.query(Assignment).filter(Assignment.membre_id == source.id).all():
        if a.creneau_id in target_asgn_slots:
            db.delete(a)
        else:
            a.membre_id = target.id

    # Stats (unique : membre × type × heure_relative) — les compteurs s'additionnent
    target_stats = {
        (s.type_evenement, s.heure_relative): s
        for s in db.query(StatsMemberHeureRelative).filter(
            StatsMemberHeureRelative.membre_id == target.id
        )
    }
    for s in db.query(StatsMemberHeureRelative).filter(
        StatsMemberHeureRelative.membre_id == source.id
    ).all():
        existing = target_stats.get((s.type_evenement, s.heure_relative))
        if existing:
            existing.fois_disponible += s.fois_disponible
            existing.fois_staffe += s.fois_staffe
            db.delete(s)
        else:
            s.membre_id = target.id

    # Respos bar désignés (unique : event × membre)
    target_respo_events = {
        r.evenement_id for r in db.query(ResponsableBar).filter(ResponsableBar.membre_id == target.id)
    }
    for r in db.query(ResponsableBar).filter(ResponsableBar.membre_id == source.id).all():
        if r.evenement_id in target_respo_events:
            db.delete(r)
        else:
            r.membre_id = target.id

    # Affinités : réattribuer, supprimer si auto-paire ou doublon
    affs = db.query(AffinityConstraint).filter(
        (AffinityConstraint.membre_a_id == source.id)
        | (AffinityConstraint.membre_b_id == source.id)
    ).all()
    seen_aff = {
        (a.evenement_id, frozenset((a.membre_a_id, a.membre_b_id)))
        for a in db.query(AffinityConstraint).filter(
            (AffinityConstraint.membre_a_id == target.id)
            | (AffinityConstraint.membre_b_id == target.id)
        )
    }
    for a in affs:
        new_a = target.id if a.membre_a_id == source.id else a.membre_a_id
        new_b = target.id if a.membre_b_id == source.id else a.membre_b_id
        key = (a.evenement_id, frozenset((new_a, new_b)))
        if new_a == new_b or key in seen_aff:
            db.delete(a)
        else:
            a.membre_a_id, a.membre_b_id = new_a, new_b
            seen_aff.add(key)

    # Alias : transférés (uniques globalement, ils appartenaient au doublon)
    db.query(MemberAlias).filter(MemberAlias.membre_id == source.id).update(
        {"membre_id": target.id}
    )
    # Le nom complet du doublon devient un alias du membre cible (futurs imports CSV)
    full_name = f"{source.prenom} {source.nom}".strip()
    if full_name and not db.query(MemberAlias).filter(MemberAlias.valeur == full_name).first():
        db.add(MemberAlias(membre_id=target.id, valeur=full_name))

    target.shifts_respo_bar_cumules = (target.shifts_respo_bar_cumules or 0) + (
        source.shifts_respo_bar_cumules or 0
    )

    db.flush()
    db.delete(source)
    db.commit()
    db.refresh(target)
    return target


@router.post("/{member_id}/reset-counters", response_model=MemberRead)
def reset_counters(
    member_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    member.shifts_respo_bar_cumules = 0
    db.query(StatsMemberHeureRelative).filter(
        StatsMemberHeureRelative.membre_id == member_id
    ).update({"fois_staffe": 0, "fois_disponible": 0})
    db.commit()
    db.refresh(member)
    return member


@router.post("/reset-all-counters", status_code=status.HTTP_204_NO_CONTENT)
def reset_all_counters(
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    db.query(Member).update({"shifts_respo_bar_cumules": 0})
    db.query(StatsMemberHeureRelative).update({"fois_staffe": 0, "fois_disponible": 0})
    db.commit()


def _saison_stats_entries(
    db: Session, member_id: int, d0: datetime, d1: datetime
) -> dict:
    """
    Recalcule les histogrammes par heure_relative sur une fenêtre de dates,
    depuis les affectations/dispos des événements publiés (la table agrégée
    StatsMemberHeureRelative n'a pas de dimension temporelle).
    """
    date_filter = (Event.statut == EventStatutEnum.publie,
                   Event.date >= d0, Event.date < d1)

    staffe_rows = (
        db.query(Event.type, Slot.heure_relative, func.count())
        .select_from(Assignment)
        .join(Slot, Assignment.creneau_id == Slot.id)
        .join(Event, Slot.evenement_id == Event.id)
        .filter(Assignment.membre_id == member_id, *date_filter)
        .group_by(Event.type, Slot.heure_relative)
        .all()
    )
    dispo_rows = (
        db.query(Event.type, Slot.heure_relative, func.count())
        .select_from(Availability)
        .join(Slot, Availability.creneau_id == Slot.id)
        .join(Event, Slot.evenement_id == Event.id)
        .filter(
            Availability.membre_id == member_id,
            Availability.statut.in_(
                [AvailabilityStatusEnum.yes, AvailabilityStatusEnum.maybe]
            ),
            *date_filter,
        )
        .group_by(Event.type, Slot.heure_relative)
        .all()
    )

    buckets: dict = {}  # (type, heure_relative) -> [dispo, staffe]
    for etype, hr, count in dispo_rows:
        buckets[(etype, hr)] = [count, 0]
    for etype, hr, count in staffe_rows:
        entry = buckets.setdefault((etype, hr), [0, 0])
        entry[1] = count
        # Les événements historiques importés (OCR) n'ont pas d'Availability :
        # être staffé implique être disponible
        entry[0] = max(entry[0], count)

    result = {EventTypeEnum.afterwork: [], EventTypeEnum.soiree: []}
    for (etype, hr), (dispo, staffe) in sorted(buckets.items(), key=lambda kv: kv[0][1]):
        result[etype].append(MemberStatsEntry(
            heure_relative=hr, fois_disponible=dispo, fois_staffe=staffe,
        ))
    return result


@router.get("/{member_id}/stats", response_model=MemberStatsRead)
def get_member_stats(
    member_id: int,
    saison_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: Member = Depends(get_current_member),
):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    bounds = _saison_bounds(db, saison_id) if saison_id is not None else None

    if bounds is not None:
        entries = _saison_stats_entries(db, member_id, *bounds)
        afterwork = entries[EventTypeEnum.afterwork]
        soiree = entries[EventTypeEnum.soiree]
    else:
        stats = db.query(StatsMemberHeureRelative).filter(
            StatsMemberHeureRelative.membre_id == member_id
        ).order_by(StatsMemberHeureRelative.heure_relative).all()

        afterwork = [
            MemberStatsEntry(
                heure_relative=s.heure_relative,
                fois_disponible=s.fois_disponible,
                fois_staffe=s.fois_staffe,
            )
            for s in stats
            if s.type_evenement == EventTypeEnum.afterwork
        ]
        soiree = [
            MemberStatsEntry(
                heure_relative=s.heure_relative,
                fois_disponible=s.fois_disponible,
                fois_staffe=s.fois_staffe,
            )
            for s in stats
            if s.type_evenement == EventTypeEnum.soiree
        ]

    def slot_labels(event_type: EventTypeEnum) -> dict:
        event = (
            db.query(Event)
            .filter(Event.statut == EventStatutEnum.publie, Event.type == event_type)
            .order_by(Event.date.desc())
            .first()
        )
        if not event:
            return {}
        return {
            s.heure_relative: s.heure_debut.strftime("%H:%M")
            for s in sorted(event.slots, key=lambda s: s.heure_debut)
        }

    # Total hours staffed from published assignments
    totals_query = (
        db.query(Event.type)
        .select_from(Assignment)
        .join(Slot, Assignment.creneau_id == Slot.id)
        .join(Event, Slot.evenement_id == Event.id)
        .filter(
            Assignment.membre_id == member_id,
            Event.statut == EventStatutEnum.publie,
        )
    )
    if bounds is not None:
        totals_query = totals_query.filter(Event.date >= bounds[0], Event.date < bounds[1])
    assignment_types = totals_query.all()
    # Convention du système : 1 créneau = 1 heure
    total_heures_afterwork = float(
        sum(1 for (t,) in assignment_types if t == EventTypeEnum.afterwork)
    )
    total_heures_soiree = float(len(assignment_types)) - total_heures_afterwork
    total_heures_cumule = total_heures_afterwork + total_heures_soiree

    return MemberStatsRead(
        afterwork=afterwork,
        soiree=soiree,
        afterwork_slot_labels=slot_labels(EventTypeEnum.afterwork),
        soiree_slot_labels=slot_labels(EventTypeEnum.soiree),
        total_heures_afterwork=round(total_heures_afterwork, 1),
        total_heures_soiree=round(total_heures_soiree, 1),
        total_heures_cumule=round(total_heures_cumule, 1),
        bien_membre=total_heures_cumule >= BIEN_MEMBRE_SEUIL_HEURES,
    )


@router.get("/{member_id}/timeline", response_model=List[TimelineEvent])
def get_member_timeline(
    member_id: int,
    saison_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: Member = Depends(get_current_member),
):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    query = (
        db.query(Assignment)
        .join(Slot, Assignment.creneau_id == Slot.id)
        .join(Event, Slot.evenement_id == Event.id)
        .filter(
            Assignment.membre_id == member_id,
            Event.statut == EventStatutEnum.publie,
        )
    )
    if saison_id is not None:
        d0, d1 = _saison_bounds(db, saison_id)
        query = query.filter(Event.date >= d0, Event.date < d1)
    assignments = query.all()

    events_map: dict = {}
    for a in assignments:
        slot = a.slot
        event = slot.event
        if event.id not in events_map:
            events_map[event.id] = {"event": event, "slots": []}
        events_map[event.id]["slots"].append(slot)

    result = []
    for _, data in sorted(
        events_map.items(),
        key=lambda x: x[1]["event"].date,
        reverse=True,
    ):
        event = data["event"]
        slots = sorted(data["slots"], key=lambda s: s.heure_debut)
        total_heures = sum(
            (s.heure_fin - s.heure_debut).total_seconds() / 3600
            for s in slots
        )
        result.append(
            TimelineEvent(
                event_id=event.id,
                nom=event.nom,
                date=event.date,
                type=event.type.value,
                slots=[
                    TimelineSlot(heure_debut=s.heure_debut, heure_fin=s.heure_fin)
                    for s in slots
                ],
                total_heures=round(total_heures, 1),
            )
        )
    return result
