"""Service partagé de création événement + créneaux."""
from __future__ import annotations

from datetime import date, datetime, time

import pytest

from app.models.models import EventStatutEnum, EventTypeEnum
from app.services.event_creation import (
    EventPublieError,
    add_slots,
    build_slot_ranges,
    new_event,
)


def test_ranges_afterwork():
    assert build_slot_ranges(date(2026, 11, 5), time(18), time(20)) == [
        (datetime(2026, 11, 5, 18), datetime(2026, 11, 5, 19)),
        (datetime(2026, 11, 5, 19), datetime(2026, 11, 5, 20)),
    ]


def test_ranges_midnight():
    ranges = build_slot_ranges(date(2026, 11, 5), time(22), time(2))
    assert len(ranges) == 4
    assert ranges[2][0] == datetime(2026, 11, 6, 0)
    assert ranges[-1][1] == datetime(2026, 11, 6, 2)


def test_ranges_truncated():
    ranges = build_slot_ranges(date(2026, 11, 5), time(18), time(19, 30))
    assert ranges[-1] == (datetime(2026, 11, 5, 19), datetime(2026, 11, 5, 19, 30))


def test_ranges_pas_30():
    assert len(build_slot_ranges(date(2026, 11, 5), time(18), time(20), 30)) == 4


def test_add_slots_heures_relatives(db_session):
    event = new_event(db_session, "Soirée", datetime(2026, 11, 5, 22), EventTypeEnum.soiree)
    assert event.public_token
    slots = add_slots(
        db_session, event, build_slot_ranges(date(2026, 11, 5), time(22), time(2)), 5
    )
    assert [s.heure_relative for s in slots] == [0, 1, 2, 3]
    assert {s.max_personnes for s in slots} == {5}


def test_add_slots_dedoublonne(db_session):
    event = new_event(db_session, "AW", datetime(2026, 11, 5, 18), EventTypeEnum.afterwork)
    ranges = build_slot_ranges(date(2026, 11, 5), time(18), time(20))
    add_slots(db_session, event, ranges, 3)
    assert len(add_slots(db_session, event, ranges, 3)) == 2


def test_add_slots_publie(db_session):
    event = new_event(db_session, "AW", datetime(2026, 11, 5, 18), EventTypeEnum.afterwork)
    event.statut = EventStatutEnum.publie
    with pytest.raises(EventPublieError):
        add_slots(
            db_session, event, build_slot_ranges(date(2026, 11, 5), time(18), time(20)), 3
        )
