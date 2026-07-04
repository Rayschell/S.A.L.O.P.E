"""Tests for the public availability poll (link, submission, pending resolution)."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.models import (
    Availability,
    AvailabilityStatusEnum,
    Event,
    EventStatutEnum,
    EventTypeEnum,
    Member,
    MemberAlias,
    PendingSubmission,
    Slot,
    StatsMemberHeureRelative,
)
from app.services import csv_import as csv_svc


def _make_event_with_slots(db: Session, n_slots: int = 2) -> tuple[Event, list[Slot]]:
    date = datetime(2026, 9, 1, 20, 0)
    event = Event(
        nom="Soirée poll",
        date=date,
        type=EventTypeEnum.soiree,
        statut=EventStatutEnum.brouillon,
    )
    db.add(event)
    db.flush()
    slots = [
        Slot(
            evenement_id=event.id,
            heure_debut=date + timedelta(hours=i),
            heure_fin=date + timedelta(hours=i + 1),
            heure_relative=i,
            max_personnes=3,
        )
        for i in range(n_slots)
    ]
    db.add_all(slots)
    db.flush()
    return event, slots


def _make_member(db: Session, prenom: str = "Marie", nom: str = "Durand") -> Member:
    member = Member(prenom=prenom, nom=nom, roles=["staff"], shifts_respo_bar_cumules=0)
    db.add(member)
    db.flush()
    return member


def _open_poll(client, event_id: int, deadline: str | None = None) -> str:
    res = client.put(f"/api/events/{event_id}/public-link", json={
        "inscriptions_ouvertes": True, "inscriptions_deadline": deadline,
    })
    assert res.status_code == 200, res.text
    return res.json()["public_token"]


def _dispo_count(db: Session, member_id: int, hr: int) -> int:
    stat = (
        db.query(StatsMemberHeureRelative)
        .filter_by(
            membre_id=member_id,
            type_evenement=EventTypeEnum.soiree,
            heure_relative=hr,
        )
        .first()
    )
    return stat.fois_disponible if stat else 0


def test_public_link_lifecycle(client, db_session: Session):
    # Event sans slot : ouverture refusée
    event_vide = Event(
        nom="Vide", date=datetime(2026, 9, 1), type=EventTypeEnum.afterwork,
        statut=EventStatutEnum.brouillon,
    )
    db_session.add(event_vide)
    db_session.flush()
    res = client.put(f"/api/events/{event_vide.id}/public-link", json={
        "inscriptions_ouvertes": True,
    })
    assert res.status_code == 400

    # Le lien est permanent : le GET fournit (et backfill) le token même fermé
    event, _ = _make_event_with_slots(db_session)
    res = client.get(f"/api/events/{event.id}/public-link")
    assert res.status_code == 200
    token = res.json()["public_token"]
    assert token
    assert res.json()["inscriptions_ouvertes"] is False
    assert res.json()["slots_count"] == 2
    # Stable entre deux GET
    assert client.get(f"/api/events/{event.id}/public-link").json()["public_token"] == token

    # L'ouverture conserve le même token
    assert _open_poll(client, event.id) == token
    res = client.put(f"/api/events/{event.id}/public-link", json={
        "inscriptions_ouvertes": True, "inscriptions_deadline": "2030-01-01T00:00:00",
    })
    assert res.json()["public_token"] == token
    assert res.json()["inscriptions_deadline"] == "2030-01-01T00:00:00"

    # Un événement créé via l'API naît avec son token
    res = client.post("/api/events", json={
        "nom": "Via API", "date": "2026-09-01T20:00:00", "type": "soiree",
    })
    created = db_session.query(Event).filter_by(id=res.json()["id"]).first()
    assert created.public_token

    # Fermeture : le token est conservé, deadline effacée (état complet au PUT)
    res = client.put(f"/api/events/{event.id}/public-link", json={
        "inscriptions_ouvertes": False,
    })
    assert res.json()["public_token"] == token
    assert res.json()["inscriptions_ouvertes"] is False
    assert res.json()["inscriptions_deadline"] is None


def test_get_poll_public(client, db_session: Session):
    event, slots = _make_event_with_slots(db_session)
    token = _open_poll(client, event.id)

    res = client.get(f"/api/public/polls/{token}")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["event_nom"] == "Soirée poll"
    assert data["ouvert"] is True
    assert [s["id"] for s in data["slots"]] == [s.id for s in slots]

    assert client.get("/api/public/polls/token-bidon").status_code == 404


def test_poll_closed_deadline_and_validation(client, db_session: Session):
    event, slots = _make_event_with_slots(db_session)
    token = _open_poll(client, event.id)
    payload = {
        "nom": "Marie Durand",
        "reponses": [{"creneau_id": slots[0].id, "statut": "yes"}],
    }

    # Toggle fermé → 403 (et le GET expose l'état)
    client.put(f"/api/events/{event.id}/public-link", json={"inscriptions_ouvertes": False})
    assert client.get(f"/api/public/polls/{token}").json()["raison_fermeture"] == "closed"
    assert client.post(f"/api/public/polls/{token}", json=payload).status_code == 403

    # Deadline passée → 410
    _open_poll(client, event.id, deadline="2020-01-01T00:00:00")
    assert client.get(f"/api/public/polls/{token}").json()["raison_fermeture"] == "deadline"
    assert client.post(f"/api/public/polls/{token}", json=payload).status_code == 410

    # Réouverture sans deadline ; creneau_id étranger → 422
    _open_poll(client, event.id)
    bad = {"nom": "X Y", "reponses": [{"creneau_id": 999999, "statut": "yes"}]}
    assert client.post(f"/api/public/polls/{token}", json=bad).status_code == 422


def test_submit_matched_and_resubmission_stats(client, db_session: Session):
    event, slots = _make_event_with_slots(db_session)
    member = _make_member(db_session)
    token = _open_poll(client, event.id)

    # Match exact "Prénom Nom"
    res = client.post(f"/api/public/polls/{token}", json={
        "nom": "Marie Durand",
        "reponses": [
            {"creneau_id": slots[0].id, "statut": "yes"},
            {"creneau_id": slots[1].id, "statut": "no"},
        ],
    })
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "matched"

    avails = {
        a.creneau_id: a.statut
        for a in db_session.query(Availability).filter_by(
            evenement_id=event.id, membre_id=member.id
        )
    }
    assert avails[slots[0].id] == AvailabilityStatusEnum.yes
    assert avails[slots[1].id] == AvailabilityStatusEnum.no
    assert _dispo_count(db_session, member.id, 0) == 1
    assert _dispo_count(db_session, member.id, 1) == 0
    assert (
        db_session.query(MemberAlias).filter_by(valeur="Marie Durand").first()
        is not None
    )

    # Re-soumission : écrase sans doubler les stats
    # slot0 yes→no (décrémente), slot1 no→maybe (incrémente)
    res = client.post(f"/api/public/polls/{token}", json={
        "nom": "Marie Durand",
        "reponses": [
            {"creneau_id": slots[0].id, "statut": "no"},
            {"creneau_id": slots[1].id, "statut": "maybe"},
        ],
    })
    assert res.json()["status"] == "matched"
    assert (
        db_session.query(Availability)
        .filter_by(evenement_id=event.id, membre_id=member.id)
        .count()
        == 2
    )
    assert _dispo_count(db_session, member.id, 0) == 0
    assert _dispo_count(db_session, member.id, 1) == 1

    # Re-soumission identique : stats stables (maybe→maybe)
    client.post(f"/api/public/polls/{token}", json={
        "nom": "Marie Durand",
        "reponses": [{"creneau_id": slots[1].id, "statut": "maybe"}],
    })
    assert _dispo_count(db_session, member.id, 1) == 1


def test_submit_fuzzy_match(client, db_session: Session):
    event, slots = _make_event_with_slots(db_session)
    member = _make_member(db_session)
    token = _open_poll(client, event.id)

    res = client.post(f"/api/public/polls/{token}", json={
        "nom": "Marie Durrand",  # faute de frappe, fuzzy ≥ seuil
        "reponses": [{"creneau_id": slots[0].id, "statut": "yes"}],
    })
    assert res.json()["status"] == "matched"
    assert (
        db_session.query(Availability)
        .filter_by(evenement_id=event.id, membre_id=member.id)
        .count()
        == 1
    )


def test_unknown_name_goes_pending(client, db_session: Session):
    event, slots = _make_event_with_slots(db_session)
    token = _open_poll(client, event.id)

    res = client.post(f"/api/public/polls/{token}", json={
        "nom": "Zorglub Xyzabc",
        "reponses": [{"creneau_id": slots[0].id, "statut": "yes"}],
    })
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "pending"
    rows = (
        db_session.query(PendingSubmission)
        .filter_by(evenement_id=event.id)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].nom_saisi == "Zorglub Xyzabc"
    # Aucune Availability créée
    assert db_session.query(Availability).filter_by(evenement_id=event.id).count() == 0

    # Re-soumission pending : update, pas de doublon
    client.post(f"/api/public/polls/{token}", json={
        "nom": "zorglub xyzabc",  # même nom, casse différente
        "reponses": [{"creneau_id": slots[0].id, "statut": "maybe"}],
    })
    rows = db_session.query(PendingSubmission).filter_by(evenement_id=event.id).all()
    assert len(rows) == 1
    assert rows[0].reponses == [{"creneau_id": slots[0].id, "statut": "maybe"}]


def test_list_resolve_and_delete_pending(client, db_session: Session):
    event, slots = _make_event_with_slots(db_session)
    member = _make_member(db_session)
    token = _open_poll(client, event.id)

    for nom in ("Zorglub Xyzabc", "Paul Nouveau"):
        client.post(f"/api/public/polls/{token}", json={
            "nom": nom,
            "reponses": [{"creneau_id": slots[0].id, "statut": "yes"}],
        })

    res = client.get(f"/api/events/{event.id}/public-submissions")
    assert res.status_code == 200, res.text
    submissions = res.json()
    assert len(submissions) == 2
    by_name = {s["csv_name"]: s for s in submissions}
    assert set(by_name) == {"Zorglub Xyzabc", "Paul Nouveau"}
    assert isinstance(by_name["Zorglub Xyzabc"]["suggestions"], list)

    # Résolution : Zorglub → membre existant, Paul Nouveau → création
    res = client.post(f"/api/events/{event.id}/public-submissions/resolve", json={
        "resolutions": [
            {
                "csv_name": "Zorglub Xyzabc",
                "member_id": member.id,
                "create_new": False,
                "availabilities": by_name["Zorglub Xyzabc"]["availabilities"],
            },
            {
                "csv_name": "Paul Nouveau",
                "create_new": True,
                "availabilities": by_name["Paul Nouveau"]["availabilities"],
            },
        ],
    })
    assert res.status_code == 200, res.text
    assert res.json()["resolved_count"] == 2

    assert db_session.query(PendingSubmission).filter_by(evenement_id=event.id).count() == 0
    nouveau = db_session.query(Member).filter_by(prenom="Paul", nom="Nouveau").first()
    assert nouveau is not None
    for mid in (member.id, nouveau.id):
        assert (
            db_session.query(Availability)
            .filter_by(evenement_id=event.id, membre_id=mid, creneau_id=slots[0].id)
            .first()
            .statut
            == AvailabilityStatusEnum.yes
        )
        assert _dispo_count(db_session, mid, 0) == 1

    # DELETE (« ignorer »)
    client.post(f"/api/public/polls/{token}", json={
        "nom": "Encore Uninconnu",
        "reponses": [{"creneau_id": slots[0].id, "statut": "yes"}],
    })
    sub_id = client.get(f"/api/events/{event.id}/public-submissions").json()[0]["id"]
    assert client.delete(
        f"/api/events/{event.id}/public-submissions/{sub_id}"
    ).status_code == 204
    assert client.delete(
        f"/api/events/{event.id}/public-submissions/{sub_id}"
    ).status_code == 404


def test_csv_double_import_does_not_double_stats(client, db_session: Session):
    """Régression du refactor delta : ré-importer le même CSV ne double plus
    fois_disponible (l'upsert d'une Availability existante n'incrémente plus)."""
    member = _make_member(db_session)
    event = Event(
        nom="Soirée CSV", date=datetime(2026, 9, 1, 20, 0),
        type=EventTypeEnum.soiree, statut=EventStatutEnum.brouillon,
    )
    db_session.add(event)
    db_session.flush()

    csv_content = (
        "#,Date(UTC),Name,UniqueCode,Country,2026-09-01 (20:00 - 21:00)\n"
        "1,2026-01-01,Marie Durand,abc,FR,yes\n"
    ).encode()

    for _ in range(2):
        result = csv_svc.import_csv(db_session, event.id, csv_content)
        assert result["imported_count"] == 1

    assert _dispo_count(db_session, member.id, 0) == 1
