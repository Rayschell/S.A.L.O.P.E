"""PNG export router."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..core.deps import get_current_member, get_db
from ..models.models import Assignment, Member, Slot
from ..routers.events import _get_event_or_404
from ..services.export_img import export_planning_png

router = APIRouter(prefix="/api/events", tags=["export"])


@router.get("/{event_id}/export-png")
def export_png(
    event_id: int,
    db: Session = Depends(get_db),
    current: Member = Depends(get_current_member),
):
    event = _get_event_or_404(db, event_id)
    slots = (
        db.query(Slot)
        .filter(Slot.evenement_id == event_id)
        .order_by(Slot.heure_debut)
        .all()
    )
    slot_ids = [s.id for s in slots]
    assignments = (
        db.query(Assignment).filter(Assignment.creneau_id.in_(slot_ids)).all()
    )
    member_ids = {a.membre_id for a in assignments}
    members = db.query(Member).filter(Member.id.in_(member_ids)).all()
    members.sort(key=lambda m: (m.nom, m.prenom))

    png_bytes = export_planning_png(event, slots, members, assignments)
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="planning-{event_id}.png"'
        },
    )
