"""Offline parser tests against committed sample filings (no network)."""

from __future__ import annotations

from datetime import date

from app.edgar.parsers import form13f, nport, ownership, schedule13dg
from tests.conftest import load


def test_13f_period():
    assert form13f.parse_period(load("form13f_primary_doc.xml")) == date(2024, 3, 31)


def test_13f_information_table_dollars():
    parsed = form13f.parse_information_table(
        load("form13f_infotable.xml"), period=date(2024, 3, 31)
    )
    assert len(parsed.holdings) == 3

    apple = parsed.holdings[0]
    assert apple.security.cusip == "037833100"
    assert apple.security.name == "APPLE INC"
    assert apple.value == 50_000_000  # already dollars (2024 filing)
    assert apple.shares == 250_000_000
    assert apple.voting_sole == 250_000_000

    put = parsed.holdings[2]
    assert put.put_call == "Put"
    assert put.voting_none == 100_000


def test_13f_value_in_thousands_normalization():
    """Pre-2023 filings report value in thousands; we scale to whole dollars."""
    parsed = form13f.parse_information_table(
        load("form13f_infotable.xml"), value_in_thousands=True
    )
    assert parsed.holdings[0].value == 50_000_000 * 1000


def test_form4_ownership():
    parsed = ownership.parse(load("form4.xml"))
    assert parsed.insider_name == "COOK TIMOTHY D"
    assert parsed.is_officer is True
    assert parsed.is_director is False
    assert getattr(parsed, "issuer_ticker") == "AAPL"
    assert parsed.issuer_cik == "0000320193"  # exact handle on the issuer
    assert len(parsed.transactions) == 1

    txn = parsed.transactions[0]
    assert txn.txn_code == "S"
    assert txn.acquired_disposed == "D"
    assert txn.shares == 100_000
    assert txn.price == 190.50
    assert txn.shares_owned_after == 3_280_000
    assert txn.txn_date == date(2024, 5, 15)


def test_nport():
    parsed = nport.parse(load("nport.xml"))
    assert parsed.period_of_report == date(2024, 3, 31)
    assert len(parsed.holdings) == 2
    msft = parsed.holdings[0]
    assert msft.security.cusip == "594918104"
    assert msft.value == 123_456_789
    assert float(msft.pct_of_net_assets) == 5.25


def test_sc13d_best_effort():
    parsed = schedule13dg.parse(load("sc13d.html"), form_type="SC 13D")
    assert parsed.issuer.cusip == "36467W109"
    assert parsed.percent_of_class == 12.5
    assert parsed.shares == 9_001_000
    assert parsed.is_activist is True
    assert parsed.event_date == date(2024, 1, 15)
