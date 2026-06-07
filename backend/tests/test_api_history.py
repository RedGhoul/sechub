"""Historical 13F profile and unified issuer-activity API endpoints.

Calls the router functions directly against an in-memory SQLite session,
passing explicit args in place of FastAPI ``Query``/``Depends`` defaults.
"""

from __future__ import annotations

from datetime import date

from app.api.routers import filers as r
from app.edgar.parsers.dto import SecurityRef
from app.ingest.resolve import get_or_create_filer, get_or_create_security
from app.models import Filing, Holding, InsiderTxn


def _add_13f(db, filer, period, positions):
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
        db.add(Holding(filing_id=filing.id, security_id=sec.id, shares=shares, value=value))
    db.flush()


def test_periods_lists_quarters_newest_first(db):
    filer = get_or_create_filer(db, "0000000001", "Test Capital")
    _add_13f(db, filer, date(2023, 12, 31), {"037833100": ("APPLE INC", 100, 1000)})
    _add_13f(db, filer, date(2024, 3, 31), {
        "037833100": ("APPLE INC", 60, 700),
        "67066G104": ("NVIDIA CORP", 50, 5000),
    })

    periods = r.filer_periods("0000000001", db)
    assert [p.period for p in periods] == [date(2024, 3, 31), date(2023, 12, 31)]
    assert periods[0].position_count == 2
    assert periods[0].total_value == 5700


def test_filer_detail_returns_requested_historical_period(db):
    filer = get_or_create_filer(db, "0000000001", "Test Capital")
    _add_13f(db, filer, date(2023, 12, 31), {"037833100": ("APPLE INC", 100, 1000)})
    _add_13f(db, filer, date(2024, 3, 31), {"67066G104": ("NVIDIA CORP", 50, 5000)})

    # Explicit older period.
    old = r.filer_detail("0000000001", period=date(2023, 12, 31), db=db)
    assert old.period_of_report == date(2023, 12, 31)
    assert old.total_value == 1000

    # Default (period=None) resolves to the latest.
    latest = r.filer_detail("0000000001", period=None, db=db)
    assert latest.period_of_report == date(2024, 3, 31)


def _add_insider_txn(db, insider_cik, insider_name, security):
    insider = get_or_create_filer(db, insider_cik, insider_name, kind="insider")
    filing = Filing(
        accession_no=f"acc-{insider_cik}",
        filer_id=insider.id,
        form_type="4",
        filed_at=date(2024, 1, 1),
        source_url="http://example/4",
    )
    db.add(filing)
    db.flush()
    db.add(
        InsiderTxn(
            filing_id=filing.id,
            security_id=security.id,
            insider_name=insider_name,
            txn_date=date(2024, 1, 1),
            acquired_disposed="A",
            shares=10,
        )
    )
    db.flush()


def test_issuer_activity_joins_by_issuer_cik(db):
    # The company files 13F under one name; insiders trade its stock recorded
    # under a *different* name string. The CIK join must still connect them.
    get_or_create_filer(db, "0000001067", "BERKSHIRE HATHAWAY INC")
    sec = get_or_create_security(
        db,
        SecurityRef(cusip="", name="Berkshire Hathaway"),
        ticker="BRK-A",
        issuer_cik="0000001067",
    )
    assert sec.issuer_cik == "0000001067"  # persisted on the row
    _add_insider_txn(db, "0000009999", "BUFFETT WARREN", sec)

    out = r.filer_issuer_activity("0000001067", limit=100, db=db)
    assert any(t.insider_name == "BUFFETT WARREN" for t in out.insider_txns)
    assert sec.id in {s.id for s in out.securities}


def test_issuer_activity_falls_back_to_name_match(db):
    # No issuer CIK on the security (e.g. from a 13D/G cover page): the name
    # match still surfaces it.
    get_or_create_filer(db, "0000001067", "BERKSHIRE HATHAWAY INC")
    sec = get_or_create_security(db, SecurityRef(cusip="084670108", name="BERKSHIRE HATHAWAY INC"))
    _add_insider_txn(db, "0000009999", "SOME INSIDER", sec)

    out = r.filer_issuer_activity("0000001067", limit=100, db=db)
    assert any(t.insider_name == "SOME INSIDER" for t in out.insider_txns)


def test_issuer_activity_empty_when_no_match(db):
    get_or_create_filer(db, "0000002000", "OBSCURE PARTNERS LP")
    out = r.filer_issuer_activity("0000002000", limit=100, db=db)
    assert out.securities == []
    assert out.insider_txns == []
    assert out.top_holders == []
