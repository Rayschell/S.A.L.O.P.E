"""Tests for the saisons CRUD and season-filtered member stats."""
from __future__ import annotations

from datetime import datetime, timedelta

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


def _make_published_event(db: Session, date: datetime, n_slots: int = 1) -> tuple[Event, list[Slot]]:
    event = Event(
        nom=f"Event {date:%Y-%m-%d}",
        date=date,
        type=EventTypeEnum.soiree,
        statut=EventStatutEnum.publie,
    )
    db.add(event)
    db.flush()
    base = date.replace(hour=20)
    slots = [
        Slot(
            evenement_id=event.id,
            heure_debut=base + timedelta(hours=i),
            heure_fin=base + timedelta(hours=i + 1),
            heure_relative=i,
            max_personnes=3,
        )
        for i in range(n_slots)
    ]
    for s in slots:
        db.add(s)
    db.flush()
    return event, slots


def _assign(db: Session, member: Member, slots: list[Slot]):
    for s in slots:
        db.add(Assignment(
            creneau_id=s.id,
            membre_id=member.id,
            type=AssignmentTypeEnum.staff,
            source=AssignmentSourceEnum.auto,
        ))
    db.flush()


def test_saison_crud(client):
    # Create
    res = client.post("/api/saisons", json={
        "nom": "Mandat 2026-2027", "date_debut": "2026-04-01", "date_fin": "2027-04-01",
    })
    assert res.status_code == 201, res.text
    saison = res.json()

    # Validation : fin <= début refusée
    res = client.post("/api/saisons", json={
        "nom": "Invalide", "date_debut": "2026-04-01", "date_fin": "2026-04-01",
    })
    assert res.status_code == 422

    # List
    res = client.get("/api/saisons")
    assert res.status_code == 200
    assert any(s["id"] == saison["id"] for s in res.json())

    # Update
    res = client.put(f"/api/saisons/{saison['id']}", json={"nom": "Mandat renommé"})
    assert res.status_code == 200
    assert res.json()["nom"] == "Mandat renommé"

    # Update invalide (fin avant début)
    res = client.put(f"/api/saisons/{saison['id']}", json={"date_fin": "2025-01-01"})
    assert res.status_code == 422

    # Delete
    res = client.delete(f"/api/saisons/{saison['id']}")
    assert res.status_code == 204
    res = client.get("/api/saisons")
    assert all(s["id"] != saison["id"] for s in res.json())

    # Saison inconnue sur les stats → 404
    res = client.get("/api/members/stats-overview", params={"saison_id": 999999})
    assert res.status_code == 404


def test_saison_en_cours_sans_date_fin(client, db_session: Session):
    """date_fin NULL = saison en cours : création, réouverture, stats non bornées."""
    # Création sans date_fin
    res = client.post("/api/saisons", json={
        "nom": "Mandat en cours", "date_debut": "2026-04-01",
    })
    assert res.status_code == 201, res.text
    saison = res.json()
    assert saison["date_fin"] is None

    # Clôture puis réouverture (date_fin=null explicite)
    res = client.put(f"/api/saisons/{saison['id']}", json={"date_fin": "2027-04-01"})
    assert res.status_code == 200
    assert res.json()["date_fin"] == "2027-04-01"
    res = client.put(f"/api/saisons/{saison['id']}", json={"date_fin": None})
    assert res.status_code == 200
    assert res.json()["date_fin"] is None

    # Les stats couvrent tout événement postérieur à date_debut, sans borne haute
    member = Member(nom="EnCours", prenom="Test", roles=["staff"], shifts_respo_bar_cumules=0)
    db_session.add(member)
    db_session.flush()
    _, before = _make_published_event(db_session, datetime(2026, 3, 1, 20, 0), n_slots=1)
    _, far_future = _make_published_event(db_session, datetime(2030, 5, 1, 20, 0), n_slots=2)
    _assign(db_session, member, before)
    _assign(db_session, member, far_future)

    res = client.get("/api/members/stats-overview", params={"saison_id": saison["id"]})
    assert res.status_code == 200, res.text
    overview = next(o for o in res.json() if o["id"] == member.id)
    assert overview["heures_total"] == 2.0

    client.delete(f"/api/saisons/{saison['id']}")


def test_stats_overview_filtre_par_saison(client, db_session: Session):
    member = Member(nom="Saison", prenom="Test", roles=["staff"], shifts_respo_bar_cumules=0)
    db_session.add(member)
    db_session.flush()

    # 1 h hors saison (2025), 10 h dans la saison 2026-2027 → badge ✦ bascule
    _, old_slots = _make_published_event(db_session, datetime(2025, 5, 1, 20, 0), n_slots=1)
    _, new_slots = _make_published_event(db_session, datetime(2026, 5, 1, 20, 0), n_slots=10)
    _assign(db_session, member, old_slots)
    _assign(db_session, member, new_slots)

    saison = client.post("/api/saisons", json={
        "nom": "2026-2027", "date_debut": "2026-04-01", "date_fin": "2027-04-01",
    }).json()
    old_saison = client.post("/api/saisons", json={
        "nom": "2025-2026", "date_debut": "2025-04-01", "date_fin": "2026-04-01",
    }).json()

    def overview_for(params=None):
        res = client.get("/api/members/stats-overview", params=params or {})
        assert res.status_code == 200, res.text
        return next(o for o in res.json() if o["id"] == member.id)

    full = overview_for()
    assert full["heures_total"] == 11.0
    assert full["bien_membre"] is True

    in_season = overview_for({"saison_id": saison["id"]})
    assert in_season["heures_total"] == 10.0
    assert in_season["bien_membre"] is True

    old_season = overview_for({"saison_id": old_saison["id"]})
    assert old_season["heures_total"] == 1.0
    assert old_season["bien_membre"] is False


def test_member_stats_saison_histogrammes_et_clamp(client, db_session: Session):
    """Season histograms are recomputed from assignments; events without
    Availability (historical OCR imports) clamp fois_disponible to fois_staffe."""
    member = Member(nom="Clamp", prenom="Test", roles=["staff"], shifts_respo_bar_cumules=0)
    db_session.add(member)
    db_session.flush()

    _, slots = _make_published_event(db_session, datetime(2026, 5, 1, 20, 0), n_slots=2)
    _assign(db_session, member, slots)  # aucune Availability créée

    saison = client.post("/api/saisons", json={
        "nom": "2026-2027", "date_debut": "2026-04-01", "date_fin": "2027-04-01",
    }).json()

    res = client.get(f"/api/members/{member.id}/stats", params={"saison_id": saison["id"]})
    assert res.status_code == 200, res.text
    stats = res.json()

    assert stats["total_heures_cumule"] == 2.0
    entries = stats["soiree"]
    assert len(entries) == 2
    for e in entries:
        assert e["fois_staffe"] == 1
        assert e["fois_disponible"] == 1, "clamp: staffé implique disponible"

    # Timeline filtrée par saison
    res = client.get(f"/api/members/{member.id}/timeline", params={"saison_id": saison["id"]})
    assert res.status_code == 200
    assert len(res.json()) == 1

    saison_vide = client.post("/api/saisons", json={
        "nom": "2027-2028", "date_debut": "2027-04-01", "date_fin": "2028-04-01",
    }).json()
    res = client.get(f"/api/members/{member.id}/timeline", params={"saison_id": saison_vide["id"]})
    assert res.status_code == 200
    assert res.json() == []
