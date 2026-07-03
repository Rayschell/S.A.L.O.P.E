"""Tests for generate_proposals (preview mode) and apply-proposal endpoint."""
from __future__ import annotations

from datetime import datetime

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
)
from app.services.scheduler import generate_proposals


def _setup_event(db: Session, n_slots: int = 2, n_members: int = 4, max_personnes: int = 2):
    event = Event(
        nom="Test Proposals",
        date=datetime(2026, 6, 1, 20, 0),
        type=EventTypeEnum.afterwork,
    )
    db.add(event)
    db.flush()

    slots = [
        Slot(
            evenement_id=event.id,
            heure_debut=datetime(2026, 6, 1, 20 + i, 0),
            heure_fin=datetime(2026, 6, 1, 21 + i, 0),
            heure_relative=i,
            max_personnes=max_personnes,
        )
        for i in range(n_slots)
    ]
    for s in slots:
        db.add(s)
    db.flush()

    members = []
    for i in range(n_members):
        m = Member(nom="Test", prenom=f"P{i}", roles=["staff"], shifts_respo_bar_cumules=0)
        db.add(m)
        db.flush()
        members.append(m)
        for s in slots:
            db.add(Availability(
                evenement_id=event.id,
                membre_id=m.id,
                creneau_id=s.id,
                statut=AvailabilityStatusEnum.yes,
            ))
    db.flush()
    return event, slots, members


def test_proposals_distinctes_et_sans_ecriture(db_session: Session):
    """Preview mode: several distinct solutions, zero DB writes."""
    event, slots, members = _setup_event(db_session)
    count_before = db_session.query(Assignment).count()

    proposals = generate_proposals(db_session, event.id, count=3)

    assert db_session.query(Assignment).count() == count_before, (
        "generate_proposals must not write assignments"
    )
    # 4 membres × 2 slots pour 2 places/slot : plusieurs optima existent
    assert len(proposals) >= 2, f"Expected at least 2 proposals, got {len(proposals)}"

    sets = [
        {(a["creneau_id"], a["membre_id"]) for a in p["assignments"]}
        for p in proposals
    ]
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            assert sets[i] != sets[j], f"Proposals {i} and {j} are identical"


def test_proposals_conservent_manuelles(db_session: Session):
    """A manual assignment must appear in every proposal."""
    event, slots, members = _setup_event(db_session)
    db_session.add(Assignment(
        creneau_id=slots[0].id,
        membre_id=members[0].id,
        type=AssignmentTypeEnum.staff,
        source=AssignmentSourceEnum.manuel,
    ))
    db_session.flush()

    proposals = generate_proposals(db_session, event.id, count=2)

    assert proposals, "Expected at least one proposal"
    for p in proposals:
        manual = [
            a for a in p["assignments"]
            if a["creneau_id"] == slots[0].id
            and a["membre_id"] == members[0].id
            and a["source"] == "manuel"
        ]
        assert manual, f"Manual assignment missing from proposal {p['index']}"


def test_apply_proposal(client, db_session: Session):
    """apply-proposal persists the chosen assignments + last_warnings."""
    event, slots, members = _setup_event(db_session)
    # Une affectation manuelle qui doit survivre à l'application
    db_session.add(Assignment(
        creneau_id=slots[0].id,
        membre_id=members[0].id,
        type=AssignmentTypeEnum.staff,
        source=AssignmentSourceEnum.manuel,
    ))
    db_session.flush()

    res = client.post(
        f"/api/events/{event.id}/generate-proposals",
        json={"excluded_member_ids": [], "count": 3},
    )
    assert res.status_code == 200, res.text
    proposals = res.json()["proposals"]
    assert proposals, "No proposals returned"
    chosen = proposals[1] if len(proposals) > 1 else proposals[0]

    res = client.post(
        f"/api/events/{event.id}/apply-proposal",
        json={
            "assignments": chosen["assignments"],
            "warnings": chosen["warnings"],
            "excluded_member_ids": [],
        },
    )
    assert res.status_code == 200, res.text

    # Les affectations en base correspondent à la proposition choisie
    slot_ids = [s.id for s in slots]
    db_asgns = {
        (a.creneau_id, a.membre_id)
        for a in db_session.query(Assignment).filter(Assignment.creneau_id.in_(slot_ids))
    }
    expected = {(a["creneau_id"], a["membre_id"]) for a in chosen["assignments"]}
    assert db_asgns == expected

    # La manuelle existe toujours, en source=manuel
    manual = (
        db_session.query(Assignment)
        .filter(
            Assignment.creneau_id == slots[0].id,
            Assignment.membre_id == members[0].id,
        )
        .first()
    )
    assert manual is not None
    assert manual.source == AssignmentSourceEnum.manuel

    # last_warnings persisté sur l'événement
    db_session.refresh(event)
    assert event.last_warnings is not None


def test_apply_proposal_creneau_etranger(client, db_session: Session):
    """A creneau_id from another event must be rejected (400)."""
    event, slots, members = _setup_event(db_session)
    other, other_slots, _ = _setup_event(db_session)

    res = client.post(
        f"/api/events/{event.id}/apply-proposal",
        json={
            "assignments": [{
                "creneau_id": other_slots[0].id,
                "membre_id": members[0].id,
                "type": "staff",
                "source": "auto",
                "maybe_force": False,
            }],
            "warnings": [],
            "excluded_member_ids": [],
        },
    )
    assert res.status_code == 400
