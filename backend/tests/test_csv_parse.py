"""Unit tests for _parse_slot_header (no DB required)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.services.csv_import import _parse_slot_header


def test_normal_slot():
    result = _parse_slot_header("2026-04-23 (17:00 - 18:00)")
    assert result is not None
    start, end = result
    assert start == datetime(2026, 4, 23, 17, 0)
    assert end == datetime(2026, 4, 23, 18, 0)
    assert end > start


def test_midnight_crossing_slot():
    """23:00 - 00:00 crosses midnight: end must be bumped to the next day."""
    result = _parse_slot_header("2026-04-23 (23:00 - 00:00)")
    assert result is not None
    start, end = result
    assert start == datetime(2026, 4, 23, 23, 0)
    assert end == datetime(2026, 4, 24, 0, 0)
    assert end == start + timedelta(hours=1)


def test_invalid_header_returns_none():
    assert _parse_slot_header("not a slot header") is None


def test_invalid_empty_returns_none():
    assert _parse_slot_header("") is None


def test_invalid_partial_returns_none():
    assert _parse_slot_header("2026-04-23") is None
