"""Router: import historical planning from an image."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..core.deps import get_db, require_bureau
from ..models.models import Member
from ..schemas.schemas import (
    HistoricalAssignment,
    HistoricalImportRequest,
    HistoricalImportResult,
    HistoricalMemberRow,
    HistoricalPreviewResponse,
    HistoricalSlot,
    HistoricalUnresolved,
    NameSuggestion,
)
from ..services import historical_img_import as svc

router = APIRouter(prefix="/api/import-historique", tags=["import-historique"])

_ALLOWED_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/bmp"}


@router.post("/preview", response_model=HistoricalPreviewResponse)
async def preview(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    """
    Parse a planning-grid image and return a structured preview.
    The frontend uses this to let the user validate before committing.
    """
    if file.content_type not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Format non supporté : {file.content_type}. Utilisez PNG, JPEG ou WEBP.",
        )

    img_bytes = await file.read()

    try:
        parsed = svc.parse_planning_image(img_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Impossible de parser l'image : {exc}",
        )

    names = [m["name"] for m in parsed["members"]]
    resolved, unresolved = svc.resolve_names(names, db)

    slots = [HistoricalSlot(**s) for s in parsed["slots"]]

    members = [
        HistoricalMemberRow(
            csv_name=m["name"],
            member_id=resolved.get(m["name"]),
            assignments=[
                HistoricalAssignment(
                    slot_index=a["slot_index"],
                    type_affectation=a["type"],
                )
                for a in m.get("assignments", [])
            ],
        )
        for m in parsed["members"]
    ]

    unresolved_out = [
        HistoricalUnresolved(
            csv_name=u["csv_name"],
            suggestions=[
                NameSuggestion(
                    member_id=s["member_id"],
                    display_name=s["display_name"],
                    score=s["score"],
                )
                for s in u.get("suggestions", [])
            ],
        )
        for u in unresolved
    ]

    return HistoricalPreviewResponse(slots=slots, members=members, unresolved=unresolved_out)


@router.post("/commit", response_model=HistoricalImportResult)
def commit(
    payload: HistoricalImportRequest,
    db: Session = Depends(get_db),
    _: Member = Depends(require_bureau),
):
    """Persist the validated historical event (published) with all assignments."""
    try:
        result = svc.commit_historical_import(
            db=db,
            event_nom=payload.event_nom,
            event_date_str=payload.event_date,
            event_type=payload.event_type,
            slots_data=[{"heure_debut": s.heure_debut, "heure_fin": s.heure_fin} for s in payload.slots],
            members_data=[
                {
                    "name": m.csv_name,
                    "assignments": [
                        {"slot_index": a.slot_index, "type": a.type_affectation}
                        for a in m.assignments
                    ],
                }
                for m in payload.members
            ],
            resolutions=[r.model_dump() for r in payload.resolutions],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    return HistoricalImportResult(**result)
