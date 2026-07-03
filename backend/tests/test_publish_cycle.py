"""Integration tests for publish / unpublish cycle via the HTTP API."""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.models import (
    Assignment,
    AssignmentSourceEnum,
    AssignmentTypeEnum,
    Availability,
    AvailabilityStatusEnum,
    Event,
    EventTypeEnum,
    Member,
    Slot,
    StatsMemberHeureRelative,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_event(db: Session) -> Event:
    event = Event(
        nom="Soiree Publish Test",
        date=datetime(2026, 7, 1, 20, 0),
        type=EventTypeEnum.soiree,
    )
    db.add(event)
    db.flush()
    return event


def _create_slot(db: Session, event_id: int, hr: int) -> Slot:
    slot = Slot(
        evenement_id=event_id,
        heure_debut=datetime(2026, 7, 1, 20 + hr, 0),
        heure_fin=datetime(2026, 7, 1, 21 + hr, 0),
        heure_relative=hr,
        max_personnes=2,
    )
    db.add(slot)
    db.flush()
    return slot


def _create_member(db: Session, prenom: str, is_respo: bool = False) -> Member:
    m = Member(
        nom="Test",
        prenom=prenom,
        roles=["staff"],
        shifts_respo_bar_cumules=0,
    )
    db.add(m)
    db.flush()
    return m


def _assign(
    db: Session,
    slot_id: int,
    member_id: int,
    atype: AssignmentTypeEnum = AssignmentTypeEnum.staff,
) -> Assignment:
    a = Assignment(
        creneau_id=slot_id,
        membre_id=member_id,
        type=atype,
        source=AssignmentSourceEnum.auto,
    )
    db.add(a)
    db.flush()
    return a


def _get_stat(db: Session, member_id: int, event_type: EventTypeEnum, hr: int):
    return (
        db.query(StatsMemberHeureRelative)
        .filter_by(
            membre_id=member_id,
            type_evenement=event_type,
            heure_relative=hr,
        )
        .first()
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_publish_increments_fois_staffe(client: TestClient, db_session: Session):
    event = _create_event(db_session)
    slot = _create_slot(db_session, event.id, hr=0)
    staff = _create_member(db_session, "Alice")
    _assign(db_session, slot.id, staff.id)

    resp = client.post(f"/api/events/{event.id}/publish")
    assert resp.status_code == 200

    stat = _get_stat(db_session, staff.id, EventTypeEnum.soiree, 0)
    assert stat is not None
    assert stat.fois_staffe == 1


def test_unpublish_restores_fois_staffe(client: TestClient, db_session: Session):
    event = _create_event(db_session)
    slot = _create_slot(db_session, event.id, hr=0)
    staff = _create_member(db_session, "Bob")
    _assign(db_session, slot.id, staff.id)

    client.post(f"/api/events/{event.id}/publish")
    stat_after_publish = _get_stat(db_session, staff.id, EventTypeEnum.soiree, 0)
    assert stat_after_publish is not None
    fois_before = stat_after_publish.fois_staffe

    resp = client.post(f"/api/events/{event.id}/unpublish")
    assert resp.status_code == 200

    db_session.expire_all()
    stat_after_unpublish = _get_stat(db_session, staff.id, EventTypeEnum.soiree, 0)
    assert stat_after_unpublish is not None
    assert stat_after_unpublish.fois_staffe == fois_before - 1


def test_publish_increments_respo_bar_counter(client: TestClient, db_session: Session):
    event = _create_event(db_session)
    slot = _create_slot(db_session, event.id, hr=0)
    respo = _create_member(db_session, "Charlie", is_respo=True)
    _assign(db_session, slot.id, respo.id, atype=AssignmentTypeEnum.respo_bar)

    initial = respo.shifts_respo_bar_cumules

    resp = client.post(f"/api/events/{event.id}/publish")
    assert resp.status_code == 200

    db_session.expire_all()
    db_session.refresh(respo)
    assert respo.shifts_respo_bar_cumules == initial + 1


def test_unpublish_restores_respo_bar_counter(client: TestClient, db_session: Session):
    event = _create_event(db_session)
    slot = _create_slot(db_session, event.id, hr=0)
    respo = _create_member(db_session, "Diana", is_respo=True)
    _assign(db_session, slot.id, respo.id, atype=AssignmentTypeEnum.respo_bar)

    client.post(f"/api/events/{event.id}/publish")
    db_session.expire_all()
    db_session.refresh(respo)
    cumul_after_publish = respo.shifts_respo_bar_cumules

    resp = client.post(f"/api/events/{event.id}/unpublish")
    assert resp.status_code == 200

    db_session.expire_all()
    db_session.refresh(respo)
    assert respo.shifts_respo_bar_cumules == cumul_after_publish - 1


def test_double_publish_returns_400(client: TestClient, db_session: Session):
    event = _create_event(db_session)
    _create_slot(db_session, event.id, hr=0)

    resp1 = client.post(f"/api/events/{event.id}/publish")
    assert resp1.status_code == 200

    resp2 = client.post(f"/api/events/{event.id}/publish")
    assert resp2.status_code == 400
