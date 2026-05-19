"""Members CRUD router."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.deps import get_db, get_current_member, require_bureau
from ..core.security import hash_password
from ..models.models import EventTypeEnum, Member, MemberAlias, StatsMemberHeureRelative
from ..schemas.schemas import (
    MemberCreate, MemberRead, MemberReadFull, MemberStatsRead, MemberStatsEntry, MemberUpdate
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
    return MemberStatsRead(afterwork=afterwork, soiree=soiree)
