"""Deterministic tests for generate_schedule (requires DB)."""
from __future__ import annotations

from datetime import datetime

import pytest
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
    ResponsableBar,
    Slot,
    StatsMemberHeureRelative,
)
from app.services.scheduler import generate_schedule


def _make_event(db: Session) -> Event:
    event = Event(
        nom="Test Soiree",
        date=datetime(2026, 6, 1, 20, 0),
        type=EventTypeEnum.soiree,
    )
    db.add(event)
    db.flush()
    return event


def _make_slots(db: Session, event_id: int, max_personnes: int = 2) -> list[Slot]:
    slots = [
        Slot(
            evenement_id=event_id,
            heure_debut=datetime(2026, 6, 1, 20 + i, 0),
            heure_fin=datetime(2026, 6, 1, 21 + i, 0),
            heure_relative=i,
            max_personnes=max_personnes,
        )
        for i in range(3)
    ]
    for s in slots:
        db.add(s)
    db.flush()
    return slots


def _make_member(db: Session, prenom: str, roles: list[str] | None = None) -> Member:
    m = Member(
        nom="Dupont",
        prenom=prenom,
        roles=roles or ["staff"],
        shifts_respo_bar_cumules=0,
    )
    db.add(m)
    db.flush()
    return m


def _set_avail(db: Session, event_id: int, member_id: int, slot_id: int, status: str):
    db.add(
        Availability(
            evenement_id=event_id,
            membre_id=member_id,
            creneau_id=slot_id,
            statut=AvailabilityStatusEnum(status),
        )
    )
    db.flush()


def test_no_overstaffing(db_session: Session):
    """Hard R6: assigned count per slot must never exceed max_personnes."""
    event = _make_event(db_session)
    slots = _make_slots(db_session, event.id, max_personnes=2)

    # 4 members, all available on all slots
    members = [_make_member(db_session, f"M{i}") for i in range(4)]
    for m in members:
        for s in slots:
            _set_avail(db_session, event.id, m.id, s.id, "yes")

    generate_schedule(db_session, event.id)

    for slot in slots:
        count = (
            db_session.query(Assignment)
            .filter(Assignment.creneau_id == slot.id)
            .count()
        )
        assert count <= slot.max_personnes, (
            f"Slot {slot.id} has {count} assignments but max_personnes={slot.max_personnes}"
        )


def test_no_assignment_on_unavailable_slot(db_session: Session):
    """Members marked 'no' on a slot must not be assigned there (unless manual)."""
    event = _make_event(db_session)
    slots = _make_slots(db_session, event.id, max_personnes=2)

    m_yes = _make_member(db_session, "Alice")
    m_no = _make_member(db_session, "Bob")

    # Alice available on all, Bob only on slot 0
    for s in slots:
        _set_avail(db_session, event.id, m_yes.id, s.id, "yes")
    _set_avail(db_session, event.id, m_no.id, slots[0].id, "yes")
    _set_avail(db_session, event.id, m_no.id, slots[1].id, "no")
    _set_avail(db_session, event.id, m_no.id, slots[2].id, "no")

    generate_schedule(db_session, event.id)

    # Bob must not appear on slots[1] or slots[2]
    for slot in slots[1:]:
        asgn = (
            db_session.query(Assignment)
            .filter(
                Assignment.creneau_id == slot.id,
                Assignment.membre_id == m_no.id,
                Assignment.source == AssignmentSourceEnum.auto,
            )
            .first()
        )
        assert asgn is None, f"Bob was auto-assigned on slot {slot.id} where he is 'no'"


def test_manual_assignment_preserved_and_counted(db_session: Session):
    """Manual assignments are kept and count toward max_personnes."""
    event = _make_event(db_session)
    slots = _make_slots(db_session, event.id, max_personnes=2)

    m_manual = _make_member(db_session, "Manuel")
    m_auto = _make_member(db_session, "Auto")

    # Both available on all slots
    for m in (m_manual, m_auto):
        for s in slots:
            _set_avail(db_session, event.id, m.id, s.id, "yes")

    # Pre-place m_manual manually on slot 0
    manual_asgn = Assignment(
        creneau_id=slots[0].id,
        membre_id=m_manual.id,
        type=AssignmentTypeEnum.staff,
        source=AssignmentSourceEnum.manuel,
    )
    db_session.add(manual_asgn)
    db_session.flush()

    generate_schedule(db_session, event.id)

    # Manual assignment must still exist
    still_there = (
        db_session.query(Assignment)
        .filter(
            Assignment.creneau_id == slots[0].id,
            Assignment.membre_id == m_manual.id,
            Assignment.source == AssignmentSourceEnum.manuel,
        )
        .first()
    )
    assert still_there is not None, "Manual assignment was deleted by the solver"

    # Total on slot 0 must not exceed max_personnes
    total = (
        db_session.query(Assignment)
        .filter(Assignment.creneau_id == slots[0].id)
        .count()
    )
    assert total <= slots[0].max_personnes, (
        f"Slot 0 has {total} assignments but max_personnes=2 (manual counts)"
    )


def test_excluded_member_not_assigned(db_session: Session):
    """A member in excluded_member_ids must never receive an auto assignment."""
    event = _make_event(db_session)
    slots = _make_slots(db_session, event.id, max_personnes=2)

    m_excl = _make_member(db_session, "Exclu")
    m_ok = _make_member(db_session, "OK")

    for m in (m_excl, m_ok):
        for s in slots:
            _set_avail(db_session, event.id, m.id, s.id, "yes")

    generate_schedule(db_session, event.id, excluded_member_ids=[m_excl.id])

    auto_asgns = (
        db_session.query(Assignment)
        .filter(
            Assignment.membre_id == m_excl.id,
            Assignment.source == AssignmentSourceEnum.auto,
        )
        .all()
    )
    assert auto_asgns == [], (
        f"Excluded member received {len(auto_asgns)} auto-assignment(s)"
    )


def test_equite_favorise_moins_staffe(db_session: Session):
    """P_equite: with equal availability, the member with a big staffing
    history stays out of a contested slot."""
    event = _make_event(db_session)
    slot = Slot(
        evenement_id=event.id,
        heure_debut=datetime(2026, 6, 1, 20, 0),
        heure_fin=datetime(2026, 6, 1, 21, 0),
        heure_relative=0,
        max_personnes=2,
    )
    db_session.add(slot)
    db_session.flush()

    m_a = _make_member(db_session, "Alice")
    m_b = _make_member(db_session, "Bob")
    m_veteran = _make_member(db_session, "Veteran")
    for m in (m_a, m_b, m_veteran):
        _set_avail(db_session, event.id, m.id, slot.id, "yes")

    # Veteran a déjà beaucoup staffé sur ce type d'événement
    db_session.add(StatsMemberHeureRelative(
        membre_id=m_veteran.id,
        type_evenement=EventTypeEnum.soiree,
        heure_relative=0,
        fois_disponible=8,
        fois_staffe=8,
    ))
    db_session.flush()

    generate_schedule(db_session, event.id)

    assigned_ids = {
        a.membre_id
        for a in db_session.query(Assignment).filter(Assignment.creneau_id == slot.id)
    }
    assert assigned_ids == {m_a.id, m_b.id}, (
        f"Expected the two least-staffed members, got {assigned_ids}"
    )


def test_rotation_respo_bar(db_session: Session):
    """P_respo_rotation: the respo candidate with the lowest cumulated respo
    shifts takes the respo pair."""
    event = _make_event(db_session)
    slots = [
        Slot(
            evenement_id=event.id,
            heure_debut=datetime(2026, 6, 1, 20 + i, 0),
            heure_fin=datetime(2026, 6, 1, 21 + i, 0),
            heure_relative=i,
            max_personnes=2,
        )
        for i in range(2)
    ]
    for s in slots:
        db_session.add(s)
    db_session.flush()

    r_busy = _make_member(db_session, "RespoFatigue")
    r_busy.shifts_respo_bar_cumules = 5
    r_fresh = _make_member(db_session, "RespoFrais")
    staffs = [_make_member(db_session, f"S{i}") for i in range(2)]
    db_session.add(ResponsableBar(evenement_id=event.id, membre_id=r_busy.id, ordre=0))
    db_session.add(ResponsableBar(evenement_id=event.id, membre_id=r_fresh.id, ordre=1))
    for m in (r_busy, r_fresh, *staffs):
        for s in slots:
            _set_avail(db_session, event.id, m.id, s.id, "yes")
    db_session.flush()

    generate_schedule(db_session, event.id)

    respo_asgns = (
        db_session.query(Assignment)
        .filter(Assignment.type == AssignmentTypeEnum.respo_bar)
        .all()
    )
    assert len(respo_asgns) == 2, "Both slots should be covered by a respo"
    assert {a.membre_id for a in respo_asgns} == {r_fresh.id}, (
        "The respo pair should go to the candidate with the lowest cumul"
    )
