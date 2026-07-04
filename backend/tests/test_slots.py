"""Tests for manual slot management (create/delete) and the no-CSV public flow."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.models import (
    Availability,
    Event,
    EventStatutEnum,
    EventTypeEnum,
    Member,
    Slot,
    StatsMemberHeureRelative,
)


def _make_event(db: Session, statut=EventStatutEnum.brouillon) -> Event:
    event = Event(
        nom="Soirée slots", date=datetime(2026, 9, 1, 20, 0),
        type=EventTypeEnum.soiree, statut=statut,
    )
    db.add(event)
    db.flush()
    return event


def test_create_slots_bulk(client, db_session: Session):
    event = _make_event(db_session)

    # Création en désordre : heure_relative recalculée triée par heure_debut
    res = client.post(f"/api/events/{event.id}/slots", json={
        "slots": [
            {"heure_debut": "2026-09-01T21:00:00", "heure_fin": "2026-09-01T22:00:00"},
            {"heure_debut": "2026-09-01T20:00:00", "heure_fin": "2026-09-01T21:00:00"},
        ],
        "max_personnes": 4,
    })
    assert res.status_code == 201, res.text
    slots = res.json()
    assert [s["heure_relative"] for s in slots] == [0, 1]
    assert slots[0]["heure_debut"] == "2026-09-01T20:00:00"
    assert all(s["max_personnes"] == 4 for s in slots)

    # Relance avec un doublon + un nouveau créneau : le doublon est ignoré
    res = client.post(f"/api/events/{event.id}/slots", json={
        "slots": [
            {"heure_debut": "2026-09-01T20:00:00", "heure_fin": "2026-09-01T21:00:00"},
            {"heure_debut": "2026-09-01T22:00:00", "heure_fin": "2026-09-01T23:00:00"},
        ],
    })
    assert res.status_code == 201
    slots = res.json()
    assert len(slots) == 3
    assert [s["heure_relative"] for s in slots] == [0, 1, 2]

    # Validation : fin <= début refusée
    res = client.post(f"/api/events/{event.id}/slots", json={
        "slots": [{"heure_debut": "2026-09-01T20:00:00", "heure_fin": "2026-09-01T20:00:00"}],
    })
    assert res.status_code == 422

    # Événement publié : verrouillé
    published = _make_event(db_session, statut=EventStatutEnum.publie)
    res = client.post(f"/api/events/{published.id}/slots", json={
        "slots": [{"heure_debut": "2026-09-01T20:00:00", "heure_fin": "2026-09-01T21:00:00"}],
    })
    assert res.status_code == 400


def test_delete_slot_decrements_stats_and_recomputes_hr(client, db_session: Session):
    event = _make_event(db_session)
    client.post(f"/api/events/{event.id}/slots", json={
        "slots": [
            {"heure_debut": "2026-09-01T20:00:00", "heure_fin": "2026-09-01T21:00:00"},
            {"heure_debut": "2026-09-01T21:00:00", "heure_fin": "2026-09-01T22:00:00"},
        ],
    })
    slots = (
        db_session.query(Slot)
        .filter_by(evenement_id=event.id)
        .order_by(Slot.heure_debut)
        .all()
    )
    member = Member(prenom="Slot", nom="Testeur", roles=["staff"], shifts_respo_bar_cumules=0)
    db_session.add(member)
    db_session.flush()
    db_session.add(Availability(
        evenement_id=event.id, membre_id=member.id, creneau_id=slots[0].id, statut="yes",
    ))
    db_session.add(StatsMemberHeureRelative(
        membre_id=member.id, type_evenement=EventTypeEnum.soiree,
        heure_relative=0, fois_disponible=1, fois_staffe=0,
    ))
    db_session.flush()

    res = client.delete(f"/api/events/{event.id}/slots/{slots[0].id}")
    assert res.status_code == 204

    # Stats décrémentées, availability partie en cascade, hr recalculée
    stat = db_session.query(StatsMemberHeureRelative).filter_by(membre_id=member.id).first()
    assert stat.fois_disponible == 0
    assert db_session.query(Availability).filter_by(evenement_id=event.id).count() == 0
    remaining = db_session.query(Slot).filter_by(evenement_id=event.id).all()
    assert len(remaining) == 1
    assert remaining[0].heure_relative == 0

    assert client.delete(f"/api/events/{event.id}/slots/999999").status_code == 404


def test_manual_slots_to_public_poll_no_csv(client, db_session: Session):
    """Scénario cible : créneaux à la main → lien public → soumission, zéro CSV."""
    event = _make_event(db_session)
    member = Member(prenom="Sans", nom="Csv", roles=["staff"], shifts_respo_bar_cumules=0)
    db_session.add(member)
    db_session.flush()

    res = client.post(f"/api/events/{event.id}/slots", json={
        "slots": [
            {"heure_debut": "2026-09-01T20:00:00", "heure_fin": "2026-09-01T21:00:00"},
            {"heure_debut": "2026-09-01T21:00:00", "heure_fin": "2026-09-01T22:00:00"},
        ],
    })
    slot_ids = [s["id"] for s in res.json()]

    token = client.put(f"/api/events/{event.id}/public-link", json={
        "inscriptions_ouvertes": True,
    }).json()["public_token"]
    assert token

    res = client.post(f"/api/public/polls/{token}", json={
        "nom": "Sans Csv",
        "reponses": [
            {"creneau_id": slot_ids[0], "statut": "yes"},
            {"creneau_id": slot_ids[1], "statut": "maybe"},
        ],
    })
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "matched"
    assert (
        db_session.query(Availability)
        .filter_by(evenement_id=event.id, membre_id=member.id)
        .count()
        == 2
    )
