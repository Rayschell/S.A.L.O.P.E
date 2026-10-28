"""Events router — CRUD, CSV import, schedule generation, assignments."""
from __future__ import annotations

import secrets
from datetime import timedelta
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
    Logo,
    Member,
    PendingSubmission,
    ResponsableBar,
    Slot,
    StatsMemberHeureRelative,
)
from ..schemas.schemas import (
    EventLogoUpdate,
    AffinityCreate,
    AffinityRead,
    ApplyProposalRequest,
    AssignmentCreate,
    AssignmentRead,
    AssignmentUpdate,
    EventCreate,
    EventDuplicateRequest,
    EventRead,
    EventReadDetail,
    EventUpdate,
    ExclusionsUpdate,
    GenerateProposalsRequest,
    GenerateProposalsResponse,
    GenerateRequest,
    GenerateResponse,
    PendingSubmissionOut,
    ProposalItem,
    SlotsBulkCreate,
    PublicLinkOut,
    PublicLinkUpdate,
    PublicResolveRequest,
    RespoBarList,
    RespoBarRead,
    SlotRead,
    SlotUpdate,
    WarningItem,
)
from ..services import csv_import as csv_svc
from ..services.event_creation import (
    EventPublieError,
    add_slots,
    new_event,
    recompute_heures_relatives,
)
from ..services import public_poll
from ..services.scheduler import (
    check_manual_assignment,
    generate_proposals,
    generate_schedule,
)

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
    event = new_event(db, payload.nom, payload.date, payload.type)
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


@router.post(
    "/{event_id}/duplicate",
    response_model=EventRead,
    status_code=status.HTTP_201_CREATED,
)
def duplicate_event(
    event_id: int,
    payload: EventDuplicateRequest,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    """
    Copie nom/type/exclusions + créneaux (max_personnes inclus) décalés vers la
    nouvelle date. Ne copie ni respos bar, ni affinités, ni disponibilités —
    l'import CSV du nouveau Strawpoll matchera les créneaux par horaires exacts
    et conservera les max_personnes copiés.
    """
    src = _get_event_or_404(db, event_id)
    new_event = Event(
        nom=payload.nom or f"{src.nom} (copie)",
        date=payload.date,
        type=src.type,
        excluded_member_ids=list(src.excluded_member_ids or []),
        public_token=secrets.token_urlsafe(16),
    )
    db.add(new_event)
    db.flush()

    # Décalage en jours entiers : les créneaux passant minuit restent cohérents
    delta = timedelta(days=(payload.date.date() - src.date.date()).days)
    for slot in db.query(Slot).filter(Slot.evenement_id == event_id).all():
        db.add(Slot(
            evenement_id=new_event.id,
            heure_debut=slot.heure_debut + delta,
            heure_fin=slot.heure_fin + delta,
            heure_relative=slot.heure_relative,
            max_personnes=slot.max_personnes,
        ))

    db.commit()
    db.refresh(new_event)
    return new_event


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
# Formulaire public de disponibilités (lien de partage + soumissions en attente)
# ---------------------------------------------------------------------------


def _public_link_out(db: Session, event: Event) -> PublicLinkOut:
    pending_count = (
        db.query(PendingSubmission)
        .filter(PendingSubmission.evenement_id == event.id)
        .count()
    )
    slots_count = db.query(Slot).filter(Slot.evenement_id == event.id).count()
    return PublicLinkOut(
        public_token=event.public_token,
        inscriptions_ouvertes=event.inscriptions_ouvertes,
        inscriptions_deadline=event.inscriptions_deadline,
        pending_count=pending_count,
        slots_count=slots_count,
    )


@router.get("/{event_id}/public-link", response_model=PublicLinkOut)
def get_public_link(
    event_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    event = _get_event_or_404(db, event_id)
    # Backfill pour les événements antérieurs à la génération du token à la création
    if event.public_token is None:
        event.public_token = secrets.token_urlsafe(16)
        db.commit()
        db.refresh(event)
    return _public_link_out(db, event)


@router.put("/{event_id}/public-link", response_model=PublicLinkOut)
def update_public_link(
    event_id: int,
    payload: PublicLinkUpdate,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    event = _get_event_or_404(db, event_id)
    if event.public_token is None:
        event.public_token = secrets.token_urlsafe(16)
    if payload.inscriptions_ouvertes:
        slots_count = db.query(Slot).filter(Slot.evenement_id == event_id).count()
        if slots_count == 0:
            raise HTTPException(
                status_code=400,
                detail="Aucun créneau : définissez-les à la création de l'événement ou importez un CSV avant d'ouvrir les inscriptions",
            )
    event.inscriptions_ouvertes = payload.inscriptions_ouvertes
    event.inscriptions_deadline = payload.inscriptions_deadline
    db.commit()
    db.refresh(event)
    return _public_link_out(db, event)


@router.get(
    "/{event_id}/public-submissions", response_model=List[PendingSubmissionOut]
)
def list_public_submissions(
    event_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    _get_event_or_404(db, event_id)
    return public_poll.list_pending(db, event_id)


@router.post("/{event_id}/public-submissions/resolve")
def resolve_public_submissions(
    event_id: int,
    payload: PublicResolveRequest,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    _get_event_or_404(db, event_id)
    # mode="json" : statuts en str, comme attendu par le service
    resolutions = [r.model_dump(mode="json") for r in payload.resolutions]
    try:
        count = public_poll.resolve_pending_submissions(db, event_id, resolutions)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"resolved_count": count}


@router.delete(
    "/{event_id}/public-submissions/{submission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_public_submission(
    event_id: int,
    submission_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    row = (
        db.query(PendingSubmission)
        .filter(
            PendingSubmission.id == submission_id,
            PendingSubmission.evenement_id == event_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Soumission introuvable")
    db.delete(row)
    db.commit()


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


@router.post(
    "/{event_id}/slots",
    response_model=List[SlotRead],
    status_code=status.HTTP_201_CREATED,
)
def create_slots(
    event_id: int,
    payload: SlotsBulkCreate,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    """Création manuelle de créneaux (alternative à l'import CSV, façon Strawpoll).

    Les doublons exacts (même heure_debut/heure_fin) sont ignorés silencieusement,
    ce qui permet de relancer un générateur sur une plage élargie.
    """
    event = _get_event_or_404(db, event_id)
    ranges = [(item.heure_debut, item.heure_fin) for item in payload.slots]
    try:
        slots = add_slots(db, event, ranges, payload.max_personnes)
    except EventPublieError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return slots


@router.delete("/{event_id}/slots/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_slot(
    event_id: int,
    slot_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    event = _get_event_or_404(db, event_id)
    if event.statut == EventStatutEnum.publie:
        raise HTTPException(
            status_code=400, detail="Événement publié : créneaux verrouillés"
        )
    slot = (
        db.query(Slot)
        .filter(Slot.evenement_id == event_id, Slot.id == slot_id)
        .first()
    )
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    # Les availabilities du créneau partent en cascade : décrémenter les stats
    # fois_disponible qu'elles avaient incrémentées (cohérence avec le delta
    # de _save_availabilities).
    avails = db.query(Availability).filter(Availability.creneau_id == slot_id).all()
    for a in avails:
        if a.statut.value in ("yes", "maybe"):
            stat = (
                db.query(StatsMemberHeureRelative)
                .filter_by(
                    membre_id=a.membre_id,
                    type_evenement=event.type,
                    heure_relative=slot.heure_relative,
                )
                .first()
            )
            if stat:
                stat.fois_disponible = max(0, stat.fois_disponible - 1)

    db.delete(slot)
    db.flush()
    recompute_heures_relatives(db, event_id)
    db.commit()


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
    body: GenerateRequest = GenerateRequest(),
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    event = _get_event_or_404(db, event_id)
    raw_warnings = generate_schedule(db, event_id, excluded_member_ids=body.excluded_member_ids)
    warnings = [
        WarningItem(
            type=w.type,
            slot_id=w.slot_id,
            member_id=w.member_id,
            message=w.message,
        )
        for w in raw_warnings
    ]
    # Persist exclusions + warnings so they survive a page reload
    event.excluded_member_ids = body.excluded_member_ids
    event.last_warnings = [w.model_dump() for w in warnings]
    db.commit()
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


@router.post("/{event_id}/generate-proposals", response_model=GenerateProposalsResponse)
def generate_proposals_endpoint(
    event_id: int,
    body: GenerateProposalsRequest = GenerateProposalsRequest(),
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    """Résout plusieurs variantes SANS rien écrire en base (mode preview)."""
    event = _get_event_or_404(db, event_id)
    if event.statut == EventStatutEnum.publie:
        raise HTTPException(status_code=400, detail="Event already published")
    count = max(2, min(body.count, 3))
    raw = generate_proposals(
        db, event_id, excluded_member_ids=body.excluded_member_ids, count=count
    )
    proposals = [
        ProposalItem(
            index=p["index"],
            score=p["score"],
            warnings=[
                WarningItem(
                    type=w.type,
                    slot_id=w.slot_id,
                    member_id=w.member_id,
                    message=w.message,
                )
                for w in p["warnings"]
            ],
            assignments=p["assignments"],
        )
        for p in raw
    ]
    return GenerateProposalsResponse(proposals=proposals)


@router.post("/{event_id}/apply-proposal", response_model=GenerateResponse)
def apply_proposal(
    event_id: int,
    body: ApplyProposalRequest,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    """Applique une proposition choisie : remplace les affectations auto."""
    event = _get_event_or_404(db, event_id)
    if event.statut == EventStatutEnum.publie:
        raise HTTPException(status_code=400, detail="Event already published")

    slot_ids = {
        s.id for s in db.query(Slot).filter(Slot.evenement_id == event_id).all()
    }
    for a in body.assignments:
        if a.creneau_id not in slot_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Créneau {a.creneau_id} n'appartient pas à cet événement",
            )

    db.query(Assignment).filter(
        Assignment.creneau_id.in_(slot_ids),
        Assignment.source == AssignmentSourceEnum.auto,
    ).delete(synchronize_session=False)
    db.flush()

    # Les affectations manuelles restent en base telles quelles ; on n'insère
    # que les entrées auto, en sautant les cellules déjà occupées (uq_assignment)
    manual_cells = {
        (a.creneau_id, a.membre_id)
        for a in db.query(Assignment)
        .filter(Assignment.creneau_id.in_(slot_ids))
        .all()
    }
    for a in body.assignments:
        if a.source != AssignmentSourceEnum.auto:
            continue
        if (a.creneau_id, a.membre_id) in manual_cells:
            continue
        db.add(Assignment(
            creneau_id=a.creneau_id,
            membre_id=a.membre_id,
            type=a.type,
            source=AssignmentSourceEnum.auto,
            maybe_force=a.maybe_force,
        ))

    event.excluded_member_ids = body.excluded_member_ids
    event.last_warnings = [w.model_dump() for w in body.warnings]
    db.commit()

    assignments = (
        db.query(Assignment).filter(Assignment.creneau_id.in_(slot_ids)).all()
    )
    return GenerateResponse(warnings=body.warnings, assignments=assignments)


# ---------------------------------------------------------------------------
# Publish (validate planning + update counters)
# ---------------------------------------------------------------------------


@router.post("/{event_id}/publish", response_model=EventRead)
def publish_event(
    event_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    # Verrou de ligne : deux publications simultanées ne doivent pas doubler les compteurs
    event = db.query(Event).filter(Event.id == event_id).with_for_update().first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
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


@router.post("/{event_id}/unpublish", response_model=EventRead)
def unpublish_event(
    event_id: int,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    """Reverse of publish: decrement the counters incremented at publication."""
    event = db.query(Event).filter(Event.id == event_id).with_for_update().first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.statut != EventStatutEnum.publie:
        raise HTTPException(status_code=400, detail="Event is not published")

    slots_map = {
        s.id: s
        for s in db.query(Slot).filter(Slot.evenement_id == event_id).all()
    }
    assignments = (
        db.query(Assignment)
        .filter(Assignment.creneau_id.in_(list(slots_map.keys())))
        .all()
    )

    respo_bar_members: set = set()
    for a in assignments:
        if a.type == AssignmentTypeEnum.respo_bar:
            respo_bar_members.add(a.membre_id)
        slot = slots_map.get(a.creneau_id)
        if not slot:
            continue
        stat = (
            db.query(StatsMemberHeureRelative)
            .filter_by(
                membre_id=a.membre_id,
                type_evenement=event.type,
                heure_relative=slot.heure_relative,
            )
            .first()
        )
        if stat and stat.fois_staffe > 0:
            stat.fois_staffe -= 1

    for member_id in respo_bar_members:
        member = db.query(Member).filter(Member.id == member_id).first()
        if member and (member.shifts_respo_bar_cumules or 0) > 0:
            member.shifts_respo_bar_cumules -= 1

    event.statut = EventStatutEnum.brouillon
    db.commit()
    db.refresh(event)
    return event


# ---------------------------------------------------------------------------
# Exclusions (members skipped by the solver)
# ---------------------------------------------------------------------------


@router.put("/{event_id}/exclusions", response_model=List[int])
def set_exclusions(
    event_id: int,
    body: ExclusionsUpdate,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    event = _get_event_or_404(db, event_id)
    event.excluded_member_ids = body.member_ids
    db.commit()
    return event.excluded_member_ids


@router.put("/{event_id}/logo", response_model=EventRead)
def set_event_logo(
    event_id: int,
    body: EventLogoUpdate,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    """Choisit le logo de l'export PNG. Autorisé même publié (n'affecte ni planning ni stats)."""
    event = _get_event_or_404(db, event_id)
    if body.logo_id is not None and db.get(Logo, body.logo_id) is None:
        raise HTTPException(status_code=404, detail="Logo introuvable")
    event.logo_id = body.logo_id
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
