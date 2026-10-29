"""Tests du vidage complet du planning (DELETE /events/{id}/assignments)."""
from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.models import (
    Assignment,
    AssignmentSourceEnum,
    AssignmentTypeEnum,
    Event,
    EventStatutEnum,
    EventTypeEnum,
    Member,
    Slot,
)


def _setup(db: Session, statut=EventStatutEnum.brouillon):
    event = Event(
        nom="Soiree Clear Test",
        date=datetime(2026, 7, 1, 20, 0),
        type=EventTypeEnum.soiree,
        statut=statut,
        last_warnings=[{"type": "W1", "slot_id": None, "member_id": None, "message": "x"}],
    )
    db.add(event)
    db.flush()
    slot = Slot(
        evenement_id=event.id,
        heure_debut=datetime(2026, 7, 1, 20, 0),
        heure_fin=datetime(2026, 7, 1, 21, 0),
        heure_relative=0,
        max_personnes=3,
    )
    db.add(slot)
    db.flush()
    for prenom, source in (("Auto", AssignmentSourceEnum.auto), ("Manu", AssignmentSourceEnum.manuel)):
        m = Member(nom="Test", prenom=prenom, roles=["staff"])
        db.add(m)
        db.flush()
        db.add(Assignment(creneau_id=slot.id, membre_id=m.id, type=AssignmentTypeEnum.staff, source=source))
    db.flush()
    return event, slot


def test_clear_removes_auto_and_manual_assignments(client: TestClient, db_session: Session):
    event, slot = _setup(db_session)

    resp = client.delete(f"/api/events/{event.id}/assignments")
    assert resp.status_code == 204

    db_session.expire_all()
    assert db_session.query(Assignment).filter_by(creneau_id=slot.id).count() == 0
    assert db_session.get(Event, event.id).last_warnings == []


def test_clear_refused_when_published(client: TestClient, db_session: Session):
    event, slot = _setup(db_session, statut=EventStatutEnum.publie)

    resp = client.delete(f"/api/events/{event.id}/assignments")
    assert resp.status_code == 400

    db_session.expire_all()
    assert db_session.query(Assignment).filter_by(creneau_id=slot.id).count() == 2
