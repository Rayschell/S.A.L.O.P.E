"""Saisons (mandats de bureau) — CRUD."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.deps import get_current_member, get_db, require_bureau
from ..models.models import Saison
from ..schemas.schemas import SaisonCreate, SaisonRead, SaisonUpdate

router = APIRouter(prefix="/api/saisons", tags=["saisons"])


def _get_or_404(db: Session, saison_id: int) -> Saison:
    saison = db.query(Saison).filter(Saison.id == saison_id).first()
    if saison is None:
        raise HTTPException(status_code=404, detail="Saison introuvable")
    return saison


@router.get("", response_model=List[SaisonRead])
def list_saisons(
    db: Session = Depends(get_db),
    _=Depends(get_current_member),
):
    return db.query(Saison).order_by(Saison.date_debut.desc()).all()


@router.post("", response_model=SaisonRead, status_code=201)
def create_saison(
    payload: SaisonCreate,
    db: Session = Depends(get_db),
    _=Depends(require_bureau),
):
    saison = Saison(**payload.model_dump())
    db.add(saison)
    db.commit()
    db.refresh(saison)
    return saison


@router.put("/{saison_id}", response_model=SaisonRead)
def update_saison(
    saison_id: int,
    payload: SaisonUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_bureau),
):
    saison = _get_or_404(db, saison_id)
    # exclude_unset (et non exclude_none) : date_fin=null explicite = saison en cours
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(saison, key, value)
    if saison.nom is None or saison.date_debut is None:
        raise HTTPException(status_code=422, detail="nom et date_debut sont requis")
    if saison.date_fin is not None and saison.date_fin <= saison.date_debut:
        raise HTTPException(
            status_code=422, detail="date_fin doit être postérieure à date_debut"
        )
    db.commit()
    db.refresh(saison)
    return saison


@router.delete("/{saison_id}", status_code=204)
def delete_saison(
    saison_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_bureau),
):
    saison = _get_or_404(db, saison_id)
    db.delete(saison)
    db.commit()
