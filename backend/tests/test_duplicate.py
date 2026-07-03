"""Tests for POST /api/events/{id}/duplicate."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.models import (
    AffinityConstraint,
    Assignment,
    Availability,
    AvailabilityStatusEnum,
    Event,
    EventStatutEnum,
    EventTypeEnum,
    Member,
    ResponsableBar,
    Slot,
)
from app.services import csv_import as csv_svc


def _setup_source(db: Session) -> tuple[Event, list[Slot], Member]:
    event = Event(
        nom="Soirée source",
        date=datetime(2026, 6, 1, 20, 0),
        type=EventTypeEnum.soiree,
        statut=EventStatutEnum.publie,
        excluded_member_ids=[42],
    )
    db.add(event)
    db.flush()

    slots = [
        # créneau normal + créneau passant minuit
        Slot(
            evenement_id=event.id,
            heure_debut=datetime(2026, 6, 1, 22, 0),
            heure_fin=datetime(2026, 6, 1, 23, 0),
            heure_relative=0,
            max_personnes=5,
        ),
        Slot(
            evenement_id=event.id,
            heure_debut=datetime(2026, 6, 1, 23, 0),
            heure_fin=datetime(2026, 6, 2, 0, 0),
            heure_relative=1,
            max_personnes=4,
        ),
    ]
    for s in slots:
        db.add(s)
    db.flush()

    member = Member(nom="Source", prenom="Membre", roles=["staff"], shifts_respo_bar_cumules=0)
    db.add(member)
    db.flush()
    # Données qui ne doivent PAS être copiées
    db.add(Availability(
        evenement_id=event.id, membre_id=member.id, creneau_id=slots[0].id,
        statut=AvailabilityStatusEnum.yes,
    ))
    db.add(ResponsableBar(evenement_id=event.id, membre_id=member.id, ordre=0))
    db.flush()
    return event, slots, member


def test_duplicate_copie_slots_et_exclusions(client, db_session: Session):
    event, slots, member = _setup_source(db_session)

    res = client.post(
        f"/api/events/{event.id}/duplicate",
        json={"nom": "Soirée copiée", "date": "2026-07-10T21:00:00"},
    )
    assert res.status_code == 201, res.text
    created = res.json()
    assert created["nom"] == "Soirée copiée"
    assert created["type"] == "soiree"
    assert created["statut"] == "brouillon"

    new_event = db_session.query(Event).filter(Event.id == created["id"]).first()
    assert list(new_event.excluded_member_ids) == [42]

    new_slots = sorted(
        db_session.query(Slot).filter(Slot.evenement_id == new_event.id).all(),
        key=lambda s: s.heure_debut,
    )
    assert len(new_slots) == 2
    # Décalage de 39 jours entiers : horaires préservés, minuit reporté à J+1
    assert new_slots[0].heure_debut == datetime(2026, 7, 10, 22, 0)
    assert new_slots[0].heure_fin == datetime(2026, 7, 10, 23, 0)
    assert new_slots[0].max_personnes == 5
    assert new_slots[1].heure_debut == datetime(2026, 7, 10, 23, 0)
    assert new_slots[1].heure_fin == datetime(2026, 7, 11, 0, 0)
    assert new_slots[1].max_personnes == 4
    assert [s.heure_relative for s in new_slots] == [0, 1]

    # Rien d'autre n'est copié
    new_slot_ids = [s.id for s in new_slots]
    assert db_session.query(Availability).filter(
        Availability.evenement_id == new_event.id
    ).count() == 0
    assert db_session.query(ResponsableBar).filter(
        ResponsableBar.evenement_id == new_event.id
    ).count() == 0
    assert db_session.query(AffinityConstraint).filter(
        AffinityConstraint.evenement_id == new_event.id
    ).count() == 0
    assert db_session.query(Assignment).filter(
        Assignment.creneau_id.in_(new_slot_ids)
    ).count() == 0


def test_duplicate_nom_par_defaut(client, db_session: Session):
    event, _, _ = _setup_source(db_session)
    res = client.post(
        f"/api/events/{event.id}/duplicate",
        json={"date": "2026-07-10T21:00:00"},
    )
    assert res.status_code == 201
    assert res.json()["nom"] == "Soirée source (copie)"


def test_duplicate_puis_import_csv_matche_slots(client, db_session: Session):
    """After duplication, a CSV import with the same times must match the
    copied slots (no duplicates) and keep the copied max_personnes."""
    event, _, _ = _setup_source(db_session)

    res = client.post(
        f"/api/events/{event.id}/duplicate",
        json={"date": "2026-07-10T21:00:00"},
    )
    assert res.status_code == 201
    new_id = res.json()["id"]

    csv_text = (
        "#,Date (UTC),Name,Unique Code,Country,"
        "2026-07-10 (22:00 - 23:00),2026-07-10 (23:00 - 00:00)\n"
        "1,2026-07-01,Personne Inconnue,abc,FR,Yes,No\n"
    )
    csv_svc.import_csv(db_session, new_id, csv_text.encode("utf-8"))

    new_slots = sorted(
        db_session.query(Slot).filter(Slot.evenement_id == new_id).all(),
        key=lambda s: s.heure_debut,
    )
    assert len(new_slots) == 2, "CSV import must match copied slots, not duplicate them"
    assert [s.max_personnes for s in new_slots] == [5, 4], (
        "max_personnes copied at duplication must survive the CSV import"
    )
