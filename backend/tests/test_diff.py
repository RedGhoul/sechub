"""Quarter-over-quarter diff and security-resolution tests (in-memory SQLite)."""

from __future__ import annotations

from datetime import date

from app.edgar.parsers.dto import SecurityRef
from app.ingest.diff import compute_changes
from app.ingest.resolve import get_or_create_filer, get_or_create_security
from app.models import Filing, Holding, HoldingChange


def _add_13f(db, filer, period, positions):
    """positions: {cusip: (name, shares, value)}."""
    filing = Filing(
        accession_no=f"{filer.cik}-{period.isoformat()}",
        filer_id=filer.id,
        form_type="13F-HR",
        filed_at=period,
        period_of_report=period,
        source_url="http://example/test",
    )
    db.add(filing)
    db.flush()
    for cusip, (name, shares, value) in positions.items():
        sec = get_or_create_security(db, SecurityRef(cusip=cusip, name=name))
        db.add(
            Holding(
                filing_id=filing.id, security_id=sec.id, shares=shares, value=value
            )
        )
    db.flush()


def test_resolve_security_dedupes_by_cusip(db):
    a = get_or_create_security(db, SecurityRef(cusip="037833100", name="APPLE INC"))
    b = get_or_create_security(db, SecurityRef(cusip="037833100", name="Apple Inc"))
    assert a.id == b.id


def test_resolve_security_by_ticker_when_no_cusip(db):
    s = get_or_create_security(db, SecurityRef(cusip="", name="Apple Inc."), ticker="AAPL")
    assert s.key == "TICKER:AAPL"


def test_diff_classifies_actions(db):
    filer = get_or_create_filer(db, "0000000001", "Test Capital")

    q1 = date(2023, 12, 31)
    q2 = date(2024, 3, 31)

    # Q1: holds AAPL and BAC.
    _add_13f(db, filer, q1, {
        "037833100": ("APPLE INC", 100, 1000),
        "060505104": ("BANK OF AMERICA", 200, 2000),
    })
    # Q2: trimmed AAPL, exited BAC, opened NVDA.
    _add_13f(db, filer, q2, {
        "037833100": ("APPLE INC", 60, 700),
        "67066G104": ("NVIDIA CORP", 50, 5000),
    })

    n = compute_changes(db, filer.id, q2)
    assert n == 3

    changes = {
        c.security.name: c
        for c in db.query(HoldingChange).filter(HoldingChange.period == q2)
    }
    assert changes["APPLE INC"].action == "TRIM"
    assert changes["APPLE INC"].shares_delta == -40
    assert changes["BANK OF AMERICA"].action == "EXIT"
    assert changes["BANK OF AMERICA"].shares_delta == -200
    assert changes["NVIDIA CORP"].action == "NEW"
    assert changes["NVIDIA CORP"].shares_delta == 50


def test_diff_is_idempotent(db):
    filer = get_or_create_filer(db, "0000000002", "Idempotent LLC")
    q1 = date(2023, 12, 31)
    q2 = date(2024, 3, 31)
    _add_13f(db, filer, q1, {"037833100": ("APPLE INC", 100, 1000)})
    _add_13f(db, filer, q2, {"037833100": ("APPLE INC", 150, 1500)})

    compute_changes(db, filer.id, q2)
    compute_changes(db, filer.id, q2)  # re-run must not duplicate
    rows = db.query(HoldingChange).filter(HoldingChange.period == q2).all()
    assert len(rows) == 1
    assert rows[0].action == "ADD"
