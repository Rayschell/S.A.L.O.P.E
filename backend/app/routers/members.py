"""Members CRUD router."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.deps import get_db, get_current_member, require_bureau
from ..core.security import hash_password
from ..models.models import (
    Assignment, Event, EventStatutEnum, EventTypeEnum,
    Member, MemberAlias, Slot, StatsMemberHeureRelative,
)
from ..schemas.schemas import (
    MemberCreate, MemberRead, MemberReadFull, MemberStatsRead, MemberStatsEntry, MemberUpdate,
    TimelineEvent, TimelineSlot, BIEN_MEMBRE_SEUIL_HEURES,
)

router = APIRouter(prefix="/api/members", tags=["members"])


@router.get("", response_model=List[MemberRead])
def list_members(
    db: Session = Depends(get_db),
    _: Member = Depends(get_current_member),
):
    return db.query(Member).order_by(Member.nom, Member.prenom).all()


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


@router.get("/{member_id}/stats", response_model=MemberStatsRead)
def get_member_stats(
    member_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(get_current_member),
):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

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
    all_assignments = (
        db.query(Assignment)
        .join(Slot, Assignment.creneau_id == Slot.id)
        .join(Event, Slot.evenement_id == Event.id)
        .filter(
            Assignment.membre_id == member_id,
            Event.statut == EventStatutEnum.publie,
        )
        .all()
    )
    total_heures_afterwork = 0.0
    total_heures_soiree = 0.0
    for a in all_assignments:
        slot = a.slot
        event = slot.event
        duration = (slot.heure_fin - slot.heure_debut).total_seconds() / 3600
        if event.type == EventTypeEnum.afterwork:
            total_heures_afterwork += duration
        else:
            total_heures_soiree += duration
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
    db: Session = Depends(get_db),
    _: Member = Depends(get_current_member),
):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    assignments = (
        db.query(Assignment)
        .join(Slot, Assignment.creneau_id == Slot.id)
        .join(Event, Slot.evenement_id == Event.id)
        .filter(
            Assignment.membre_id == member_id,
            Event.statut == EventStatutEnum.publie,
        )
        .all()
    )

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
