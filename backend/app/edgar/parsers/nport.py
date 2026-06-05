"""Parse NPORT-P monthly fund/ETF portfolio reports.

The primary_doc.xml carries a reporting period and an ``invstOrSecs`` list of
``invstOrSec`` holdings (name, CUSIP, USD value, balance, percent of net
assets). N-PORT files can be large; we stream by local-name matching.
"""

from __future__ import annotations

from datetime import date, datetime

from lxml import etree

from app.edgar.parsers.dto import FundHoldingRow, NportFiling, SecurityRef
from app.edgar.parsers.xmlutil import iter_named, text


def parse(xml: bytes) -> NportFiling:
    root = etree.fromstring(xml)

    period = _parse_date(text(root, "repPdDate")) or _parse_date(text(root, "repPdEnd"))
    holdings: list[FundHoldingRow] = []

    for sec in iter_named(root, "invstOrSec"):
        name = text(sec, "name") or text(sec, "title") or ""
        cusip = (text(sec, "cusip") or "").strip().upper()
        holdings.append(
            FundHoldingRow(
                security=SecurityRef(cusip=cusip[:9] if cusip else "", name=name),
                value=_to_int(text(sec, "valUSD")),
                balance=_to_float(text(sec, "balance")),
                pct_of_net_assets=_to_float(text(sec, "pctVal")),
            )
        )

    return NportFiling(period_of_report=period, holdings=holdings)


def _to_int(value: str | None) -> int:
    if not value:
        return 0
    try:
        return int(float(value.replace(",", "").strip()))
    except ValueError:
        return 0


def _to_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value.replace(",", "").strip())
    except ValueError:
        return None


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%m-%d-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None
