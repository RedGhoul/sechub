"""Parse NPORT-P monthly fund/ETF portfolio reports.

The primary_doc.xml carries a reporting period and an ``invstOrSecs`` list of
``invstOrSec`` holdings (name, CUSIP, USD value, balance, percent of net
assets). N-PORT files can be large; we stream by local-name matching.
"""

from __future__ import annotations

from datetime import date, datetime
from io import BytesIO

from lxml import etree

from app.edgar.parsers.dto import FundHoldingRow, NportFiling, SecurityRef
from app.edgar.parsers.xmlutil import local_name, text


def parse(xml: bytes) -> NportFiling:
    """Stream the holdings out of an N-PORT primary doc.

    These files routinely run to tens of MB, so we use ``iterparse`` and free
    each ``invstOrSec`` subtree (and its already-processed siblings) as we go,
    keeping memory bounded rather than building the whole tree at once."""
    period: date | None = None
    holdings: list[FundHoldingRow] = []

    context = etree.iterparse(BytesIO(xml), events=("end",), recover=True, huge_tree=True)
    for _event, elem in context:
        tag = local_name(elem.tag).lower()
        if tag in ("reppddate", "reppdend"):
            if period is None:
                period = _parse_date(text(elem))
        elif tag == "invstorsec":
            name = text(elem, "name") or text(elem, "title") or ""
            cusip = (text(elem, "cusip") or "").strip().upper()
            holdings.append(
                FundHoldingRow(
                    security=SecurityRef(cusip=cusip[:9] if cusip else "", name=name),
                    value=_to_int(text(elem, "valUSD")),
                    balance=_to_float(text(elem, "balance")),
                    pct_of_net_assets=_to_float(text(elem, "pctVal")),
                )
            )
            # Release this holding's subtree and any earlier siblings.
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]

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
