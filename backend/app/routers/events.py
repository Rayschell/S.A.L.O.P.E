"""Events router — CRUD, CSV import, schedule generation, assignments."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..core.deps import get_current_member, get_db, require_bureau
from ..models.models import (
    AffinityConstraint,
    Assignment,
    AssignmentSourceEnum,
    AssignmentTypeEnum,
    Availability,
    Event,
    EventStatutEnum,
    EventTypeEnum,
    Member,
    ResponsableBar,
    Slot,
    StatsMemberHeureRelative,
)
from ..schemas.schemas import (
    AffinityCreate,
    AffinityRead,
    AssignmentCreate,
    AssignmentRead,
    AssignmentUpdate,
    EventCreate,
    EventRead,
    EventReadDetail,
    EventUpdate,
    GenerateResponse,
    RespoBarList,
    RespoBarRead,
    SlotRead,
    SlotUpdate,
    WarningItem,
)
from ..services import csv_import as csv_svc
from ..services.scheduler import generate_schedule, check_manual_assignment

router = APIRouter(prefix="/api/events", tags=["events"])


# ---------------------------------------------------------------------------
# Event CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=List[EventRead])
def list_events(
    db: Session = Depends(get_db),
    _: Member = Depends(get_current_member),
):
    return db.query(Event).order_by(Event.date.desc()).all()


@router.post("", response_model=EventRead, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    event = Event(nom=payload.nom, date=payload.date, type=payload.type)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/{event_id}", response_model=EventReadDetail)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(get_current_member),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.put("/{event_id}", response_model=EventRead)
def update_event(
    event_id: int,
    payload: EventUpdate,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(event, field, value)
    db.commit()
    db.refresh(event)
    return event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(event)
    db.commit()


# ---------------------------------------------------------------------------
# CSV import
# ---------------------------------------------------------------------------


@router.post("/{event_id}/import-csv")
async def import_csv(
    event_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    _get_event_or_404(db, event_id)
    content = await file.read()
    result = csv_svc.import_csv(db, event_id, content)
    return result


@router.post("/{event_id}/resolve-pending")
def resolve_pending(
    event_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    """
    Expected body:
    {
      "resolutions": [
        {
          "csv_name": "...",
          "member_id": 3,          // or null if create_new
          "create_new": false,
          "availabilities": [{"slot_label": "...", "statut": "yes"}]
        }
      ]
    }
    """
    _get_event_or_404(db, event_id)
    slot_label_map = csv_svc.get_slot_label_map(db, event_id)
    resolutions = payload.get("resolutions", [])
    count = csv_svc.resolve_pending(db, event_id, resolutions, slot_label_map)
    return {"imported_count": count}


# ---------------------------------------------------------------------------
# Slots
# ---------------------------------------------------------------------------


@router.get("/{event_id}/slots", response_model=List[SlotRead])
def list_slots(
    event_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(get_current_member),
):
    _get_event_or_404(db, event_id)
    return (
        db.query(Slot)
        .filter(Slot.evenement_id == event_id)
        .order_by(Slot.heure_debut)
        .all()
    )


@router.put("/{event_id}/slots/{slot_id}", response_model=SlotRead)
def update_slot(
    event_id: int,
    slot_id: int,
    payload: SlotUpdate,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    slot = (
        db.query(Slot)
        .filter(Slot.evenement_id == event_id, Slot.id == slot_id)
        .first()
    )
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    slot.max_personnes = payload.max_personnes
    db.commit()
    db.refresh(slot)
    return slot


# ---------------------------------------------------------------------------
# Respos bar
# ---------------------------------------------------------------------------


@router.get("/{event_id}/respos-bar", response_model=List[RespoBarRead])
def list_respos_bar(
    event_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(get_current_member),
):
    _get_event_or_404(db, event_id)
    return (
        db.query(ResponsableBar)
        .filter(ResponsableBar.evenement_id == event_id)
        .order_by(ResponsableBar.ordre)
        .all()
    )


@router.put("/{event_id}/respos-bar", response_model=List[RespoBarRead])
def set_respos_bar(
    event_id: int,
    payload: RespoBarList,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    _get_event_or_404(db, event_id)
    db.query(ResponsableBar).filter(ResponsableBar.evenement_id == event_id).delete()
    for entry in payload.respos:
        db.add(
            ResponsableBar(
                evenement_id=event_id,
                membre_id=entry.membre_id,
                ordre=entry.ordre,
            )
        )
    db.commit()
    return (
        db.query(ResponsableBar)
        .filter(ResponsableBar.evenement_id == event_id)
        .order_by(ResponsableBar.ordre)
        .all()
    )


# ---------------------------------------------------------------------------
# Affinities
# ---------------------------------------------------------------------------


@router.get("/{event_id}/affinities", response_model=List[AffinityRead])
def list_affinities(
    event_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(get_current_member),
):
    _get_event_or_404(db, event_id)
    return db.query(AffinityConstraint).filter(AffinityConstraint.evenement_id == event_id).all()


@router.post(
    "/{event_id}/affinities",
    response_model=AffinityRead,
    status_code=status.HTTP_201_CREATED,
)
def add_affinity(
    event_id: int,
    payload: AffinityCreate,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    _get_event_or_404(db, event_id)
    if payload.membre_a_id == payload.membre_b_id:
        raise HTTPException(status_code=400, detail="Both member IDs must be different")
    # Prevent duplicate (either direction)
    existing = (
        db.query(AffinityConstraint)
        .filter(
            AffinityConstraint.evenement_id == event_id,
            (
                (AffinityConstraint.membre_a_id == payload.membre_a_id)
                & (AffinityConstraint.membre_b_id == payload.membre_b_id)
            )
            | (
                (AffinityConstraint.membre_a_id == payload.membre_b_id)
                & (AffinityConstraint.membre_b_id == payload.membre_a_id)
            ),
        )
        .first()
    )
    if existing:
        return existing
    aff = AffinityConstraint(
        evenement_id=event_id,
        membre_a_id=payload.membre_a_id,
        membre_b_id=payload.membre_b_id,
    )
    db.add(aff)
    db.commit()
    db.refresh(aff)
    return aff


@router.delete("/{event_id}/affinities/{aff_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_affinity(
    event_id: int,
    aff_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    aff = (
        db.query(AffinityConstraint)
        .filter(
            AffinityConstraint.evenement_id == event_id,
            AffinityConstraint.id == aff_id,
        )
        .first()
    )
    if not aff:
        raise HTTPException(status_code=404, detail="Affinity not found")
    db.delete(aff)
    db.commit()


# ---------------------------------------------------------------------------
# Assignments (manual overrides)
# ---------------------------------------------------------------------------


@router.get("/{event_id}/assignments", response_model=List[AssignmentRead])
def list_assignments(
    event_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(get_current_member),
):
    _get_event_or_404(db, event_id)
    slot_ids = [
        s.id
        for s in db.query(Slot).filter(Slot.evenement_id == event_id).all()
    ]
    return (
        db.query(Assignment)
        .filter(Assignment.creneau_id.in_(slot_ids))
        .all()
    )


@router.post(
    "/{event_id}/assignments",
    response_model=AssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def add_assignment(
    event_id: int,
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    _get_event_or_404(db, event_id)
    error = check_manual_assignment(db, event_id, payload.membre_id, payload.creneau_id)
    if error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error)
    slot = db.query(Slot).filter(
        Slot.id == payload.creneau_id, Slot.evenement_id == event_id
    ).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    existing = db.query(Assignment).filter(
        Assignment.creneau_id == payload.creneau_id,
        Assignment.membre_id == payload.membre_id,
    ).first()
    if existing:
        existing.type = payload.type
        existing.source = AssignmentSourceEnum.manuel
        db.commit()
        db.refresh(existing)
        return existing
    asgn = Assignment(
        creneau_id=payload.creneau_id,
        membre_id=payload.membre_id,
        type=payload.type,
        source=AssignmentSourceEnum.manuel,
    )
    db.add(asgn)
    db.commit()
    db.refresh(asgn)
    return asgn


@router.put("/{event_id}/assignments/{asgn_id}", response_model=AssignmentRead)
def update_assignment(
    event_id: int,
    asgn_id: int,
    payload: AssignmentUpdate,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    _get_event_or_404(db, event_id)
    asgn = db.query(Assignment).filter(Assignment.id == asgn_id).first()
    if not asgn:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if payload.type is not None:
        asgn.type = payload.type
    if payload.maybe_force is not None:
        asgn.maybe_force = payload.maybe_force
    asgn.source = AssignmentSourceEnum.manuel
    db.commit()
    db.refresh(asgn)
    return asgn


@router.delete("/{event_id}/assignments/{asgn_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(
    event_id: int,
    asgn_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    _get_event_or_404(db, event_id)
    asgn = db.query(Assignment).filter(Assignment.id == asgn_id).first()
    if not asgn:
        raise HTTPException(status_code=404, detail="Assignment not found")
    db.delete(asgn)
    db.commit()


@router.get("/{event_id}/availabilities")
def list_availabilities(
    event_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    _get_event_or_404(db, event_id)
    slot_ids = [s.id for s in db.query(Slot).filter(Slot.evenement_id == event_id).all()]
    if not slot_ids:
        return []
    avs = db.query(Availability).filter(Availability.creneau_id.in_(slot_ids)).all()
    return [{"membre_id": a.membre_id, "creneau_id": a.creneau_id, "statut": a.statut} for a in avs]


# ---------------------------------------------------------------------------
# Schedule generation
# ---------------------------------------------------------------------------


@router.post("/{event_id}/generate", response_model=GenerateResponse)
def generate(
    event_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    _get_event_or_404(db, event_id)
    raw_warnings = generate_schedule(db, event_id)
    warnings = [
        WarningItem(
            type=w.type,
            slot_id=w.slot_id,
            member_id=w.member_id,
            message=w.message,
        )
        for w in raw_warnings
    ]
    slot_ids = [
        s.id
        for s in db.query(Slot).filter(Slot.evenement_id == event_id).all()
    ]
    assignments = (
        db.query(Assignment)
        .filter(Assignment.creneau_id.in_(slot_ids))
        .all()
    )
    return GenerateResponse(warnings=warnings, assignments=assignments)


# ---------------------------------------------------------------------------
# Publish (validate planning + update counters)
# ---------------------------------------------------------------------------


@router.post("/{event_id}/publish", response_model=EventRead)
def publish_event(
    event_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    event = _get_event_or_404(db, event_id)
    if event.statut == EventStatutEnum.publie:
        raise HTTPException(status_code=400, detail="Event already published")

    slot_ids = [s.id for s in db.query(Slot).filter(Slot.evenement_id == event_id).all()]
    assignments = (
        db.query(Assignment).filter(Assignment.creneau_id.in_(slot_ids)).all()
    )

    # Track respo_bar members for this event
    respo_bar_members: set = set()

    slots_map = {
        s.id: s
        for s in db.query(Slot).filter(Slot.evenement_id == event_id).all()
    }

    for a in assignments:
        if a.type == AssignmentTypeEnum.respo_bar:
            respo_bar_members.add(a.membre_id)
        slot = slots_map.get(a.creneau_id)
        if not slot:
            continue
        hr = slot.heure_relative
        stat = (
            db.query(StatsMemberHeureRelative)
            .filter_by(
                membre_id=a.membre_id,
                type_evenement=event.type,
                heure_relative=hr,
            )
            .first()
        )
        if stat:
            stat.fois_staffe += 1
        else:
            db.add(StatsMemberHeureRelative(
                membre_id=a.membre_id,
                type_evenement=event.type,
                heure_relative=hr,
                fois_disponible=0,
                fois_staffe=1,
            ))

    for member_id in respo_bar_members:
        member = db.query(Member).filter(Member.id == member_id).first()
        if member:
            member.shifts_respo_bar_cumules = (member.shifts_respo_bar_cumules or 0) + 1

    event.statut = EventStatutEnum.publie
    db.commit()
    db.refresh(event)
    return event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_event_or_404(db: Session, event_id: int) -> Event:
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event
