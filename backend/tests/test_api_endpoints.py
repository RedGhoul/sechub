"""REST endpoint tests for the filings, securities, and filer routers.

Follows the project convention of calling router functions directly against an
in-memory SQLite session, passing explicit args in place of FastAPI
``Query``/``Depends`` defaults.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException

from app.api.routers import filers as fr
from app.api.routers import filings as fl
from app.api.routers import securities as sr
from app.edgar.parsers.dto import SecurityRef
from app.ingest.diff import compute_changes
from app.ingest.resolve import get_or_create_filer, get_or_create_security
from app.models import (
    Filing,
    FundHolding,
    Holding,
    OwnershipStake,
)


# --- small builders -------------------------------------------------------


def _filing(db, filer, form, filed_at, period=None, accession=None):
    filing = Filing(
        accession_no=accession or f"{filer.cik}-{form}-{filed_at.isoformat()}",
        filer_id=filer.id,
        form_type=form,
        filed_at=filed_at,
        period_of_report=period,
        source_url=f"http://example/{form}",
    )
    db.add(filing)
    db.flush()
    return filing


def _add_13f(db, filer, period, positions):
    filing = _filing(db, filer, "13F-HR", period, period)
    for cusip, (name, shares, value) in positions.items():
        sec = get_or_create_security(db, SecurityRef(cusip=cusip, name=name))
        db.add(Holding(filing_id=filing.id, security_id=sec.id, shares=shares, value=value))
    db.flush()
    return filing


# --- filings feed ---------------------------------------------------------


def test_feed_returns_filings_newest_first(db):
    filer = get_or_create_filer(db, "0000000001", "Test Capital")
    _filing(db, filer, "13F-HR", date(2024, 1, 1))
    _filing(db, filer, "4", date(2024, 3, 1))

    out = fl.feed(form=None, since=None, limit=50, db=db)
    assert [f.form_type for f in out] == ["4", "13F-HR"]
    # The filer relationship is serialized too.
    assert out[0].filer.cik == "0000000001"


def test_feed_filters_by_exact_form(db):
    filer = get_or_create_filer(db, "0000000001", "Test Capital")
    _filing(db, filer, "13F-HR", date(2024, 1, 1))
    _filing(db, filer, "4", date(2024, 3, 1))

    out = fl.feed(form="4", since=None, limit=50, db=db)
    assert [f.form_type for f in out] == ["4"]


def test_feed_filters_by_since_date(db):
    filer = get_or_create_filer(db, "0000000001", "Test Capital")
    _filing(db, filer, "13F-HR", date(2024, 1, 1))
    _filing(db, filer, "4", date(2024, 3, 1))

    out = fl.feed(form=None, since=date(2024, 2, 1), limit=50, db=db)
    assert [f.filed_at for f in out] == [date(2024, 3, 1)]


def test_feed_respects_limit(db):
    filer = get_or_create_filer(db, "0000000001", "Test Capital")
    for i in range(1, 6):
        _filing(db, filer, "4", date(2024, 1, i), accession=f"acc-{i}")

    out = fl.feed(form=None, since=None, limit=2, db=db)
    assert len(out) == 2


def test_filing_detail_returns_one(db):
    filer = get_or_create_filer(db, "0000000001", "Test Capital")
    f = _filing(db, filer, "13F-HR", date(2024, 1, 1), period=date(2023, 12, 31))

    out = fl.filing_detail(f.id, db=db)
    assert out.id == f.id
    assert out.period_of_report == date(2023, 12, 31)


def test_filing_detail_404_when_missing(db):
    with pytest.raises(HTTPException) as exc:
        fl.filing_detail(99999, db=db)
    assert exc.value.status_code == 404


# --- securities holders ---------------------------------------------------


def test_holders_ranked_by_value_latest_position(db):
    big = get_or_create_filer(db, "0000000001", "Big Fund")
    small = get_or_create_filer(db, "0000000002", "Small Fund")

    # Big holds more value; both report the same Apple CUSIP.
    _add_13f(db, big, date(2024, 3, 31), {"037833100": ("APPLE INC", 1000, 9000)})
    _add_13f(db, small, date(2024, 3, 31), {"037833100": ("APPLE INC", 100, 1000)})

    out = sr.holders("037833100", db=db)
    assert [h.filer.name for h in out] == ["Big Fund", "Small Fund"]
    assert out[0].value == 9000


def test_holders_uses_only_latest_period_per_filer(db):
    filer = get_or_create_filer(db, "0000000001", "Test Capital")
    _add_13f(db, filer, date(2023, 12, 31), {"037833100": ("APPLE INC", 100, 1000)})
    _add_13f(db, filer, date(2024, 3, 31), {"037833100": ("APPLE INC", 50, 700)})

    out = sr.holders("037833100", db=db)
    assert len(out) == 1
    assert out[0].period_of_report == date(2024, 3, 31)
    assert out[0].shares == 50


def test_holders_cusip_lookup_is_case_insensitive(db):
    filer = get_or_create_filer(db, "0000000001", "Test Capital")
    _add_13f(db, filer, date(2024, 3, 31), {"36467W109": ("SOME CO", 10, 100)})

    out = sr.holders("36467w109", db=db)  # lowercased input
    assert len(out) == 1


def test_holders_404_for_unknown_cusip(db):
    with pytest.raises(HTTPException) as exc:
        sr.holders("000000000", db=db)
    assert exc.value.status_code == 404


# --- filer list / search --------------------------------------------------


def test_list_filers_filters_by_name_substring(db):
    get_or_create_filer(db, "0000000001", "Berkshire Hathaway")
    get_or_create_filer(db, "0000000002", "Scion Asset Management")

    out = fr.list_filers(q="scion", kind=None, limit=50, db=db)
    assert [f.name for f in out] == ["Scion Asset Management"]


def test_list_filers_filters_by_kind(db):
    get_or_create_filer(db, "0000000001", "An Institution", kind="institution")
    get_or_create_filer(db, "0000000002", "An Insider", kind="insider")

    out = fr.list_filers(q=None, kind="insider", limit=50, db=db)
    assert {f.kind for f in out} == {"insider"}


# --- filer resolution / 404 ----------------------------------------------


def test_filer_detail_404_for_unknown_cik(db):
    with pytest.raises(HTTPException) as exc:
        fr.filer_detail("0000009999", period=None, db=db)
    assert exc.value.status_code == 404


def test_filer_detail_empty_when_no_13f_on_record(db):
    get_or_create_filer(db, "0000000001", "No Holdings LP")
    out = fr.filer_detail("0000000001", period=None, db=db)
    assert out.position_count == 0
    assert out.total_value == 0
    assert out.holdings == []


def test_filer_detail_computes_pct_of_portfolio(db):
    filer = get_or_create_filer(db, "0000000001", "Test Capital")
    _add_13f(
        db,
        filer,
        date(2024, 3, 31),
        {
            "037833100": ("APPLE INC", 100, 7500),
            "67066G104": ("NVIDIA CORP", 50, 2500),
        },
    )
    out = fr.filer_detail("0000000001", period=None, db=db)
    assert out.total_value == 10000
    # Sorted by value desc, so Apple (75%) leads.
    assert out.holdings[0].security.name == "APPLE INC"
    assert out.holdings[0].pct_of_portfolio == 75.0
    assert out.holdings[1].pct_of_portfolio == 25.0


# --- filer changes --------------------------------------------------------


def test_filer_changes_defaults_to_latest_period(db):
    filer = get_or_create_filer(db, "0000000001", "Test Capital")
    _add_13f(db, filer, date(2023, 12, 31), {"037833100": ("APPLE INC", 100, 1000)})
    _add_13f(db, filer, date(2024, 3, 31), {"037833100": ("APPLE INC", 150, 1500)})
    compute_changes(db, filer.id, date(2024, 3, 31))

    out = fr.filer_changes("0000000001", period=None, db=db)
    assert out.period == date(2024, 3, 31)
    assert out.prev_period == date(2023, 12, 31)
    assert [c.action for c in out.changes] == ["ADD"]
    assert out.changes[0].shares_delta == 50


def test_filer_changes_empty_when_none_computed(db):
    get_or_create_filer(db, "0000000001", "Test Capital")
    out = fr.filer_changes("0000000001", period=None, db=db)
    assert out.changes == []


# --- fund holdings --------------------------------------------------------


def _add_nport(db, filer, period, rows):
    filing = _filing(db, filer, "NPORT-P", period, period)
    for cusip, (name, value, pct) in rows.items():
        sec = get_or_create_security(db, SecurityRef(cusip=cusip, name=name))
        db.add(
            FundHolding(
                filing_id=filing.id,
                security_id=sec.id,
                value=value,
                pct_of_net_assets=pct,
            )
        )
    db.flush()


def test_fund_holdings_latest_period_sorted_by_value(db):
    fund = get_or_create_filer(db, "0000000001", "Some ETF", kind="fund")
    _add_nport(
        db,
        fund,
        date(2024, 3, 31),
        {
            "594918104": ("MICROSOFT", 5000, 5.25),
            "037833100": ("APPLE INC", 9000, 7.0),
        },
    )
    out = fr.filer_fund_holdings("0000000001", period=None, limit=500, db=db)
    assert [h.security.name for h in out] == ["APPLE INC", "MICROSOFT"]
    assert out[0].pct_of_net_assets == 7.0


def test_fund_holdings_empty_when_no_nport(db):
    get_or_create_filer(db, "0000000001", "Equity Fund", kind="fund")
    out = fr.filer_fund_holdings("0000000001", period=None, limit=500, db=db)
    assert out == []


# --- stakes held ----------------------------------------------------------


def test_stakes_held_returns_activist_flag(db):
    filer = get_or_create_filer(db, "0000000001", "Activist Partners")
    filing = _filing(db, filer, "SC 13D", date(2024, 1, 15))
    sec = get_or_create_security(db, SecurityRef(cusip="36467W109", name="TARGET CO"))
    db.add(
        OwnershipStake(
            filing_id=filing.id,
            security_id=sec.id,
            percent_of_class=12.5,
            shares=9_001_000,
            event_date=date(2024, 1, 15),
            is_activist=True,
        )
    )
    db.flush()

    out = fr.filer_stakes_held("0000000001", limit=200, db=db)
    assert len(out) == 1
    assert out[0].form_type == "SC 13D"
    assert out[0].is_activist is True
    assert out[0].percent_of_class == 12.5


def test_stakes_held_empty_for_filer_without_stakes(db):
    get_or_create_filer(db, "0000000001", "Plain Vanilla LP")
    assert fr.filer_stakes_held("0000000001", limit=200, db=db) == []
