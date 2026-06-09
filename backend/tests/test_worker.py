"""Offline tests for the continuous worker's scheduling decision.

``_backfill_due`` is the only non-trivial logic in the loop (the rest is I/O),
so we pin its once-per-UTC-day behavior here without touching the network or DB.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app import worker
from app.config import settings


@pytest.fixture(autouse=True)
def _fixed_backfill_hour(monkeypatch):
    # Decouple the assertions from whatever the environment configures.
    monkeypatch.setattr(settings, "sechub_backfill_hour", 5)


def _utc(year: int, month: int, day: int, hour: int) -> datetime:
    return datetime(year, month, day, hour, 0, tzinfo=timezone.utc)


def test_due_on_first_cycle_at_or_after_the_hour():
    assert worker._backfill_due(None, _utc(2024, 6, 1, 5)) is True
    assert worker._backfill_due(None, _utc(2024, 6, 1, 9)) is True


def test_not_due_before_the_hour():
    assert worker._backfill_due(None, _utc(2024, 6, 1, 4)) is False


def test_not_due_again_once_it_has_run_today():
    assert worker._backfill_due(date(2024, 6, 1), _utc(2024, 6, 1, 23)) is False


def test_due_again_on_a_new_day():
    assert worker._backfill_due(date(2024, 6, 1), _utc(2024, 6, 2, 5)) is True
