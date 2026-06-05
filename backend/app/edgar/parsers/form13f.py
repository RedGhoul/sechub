"""Parse 13F-HR filings: the cover (primary_doc.xml) and the information table.

The information table is a list of ``infoTable`` elements, each a position:
issuer name, CUSIP, value, share/principal amount + type, optional put/call,
investment discretion, and voting authority (sole/shared/none).

Value normalization: filings before the SEC's 2023 amendment report ``value``
in **thousands of dollars**; later ones report whole dollars. The pipeline
passes ``value_in_thousands`` (derived from the filing date) so we store USD.
"""

from __future__ import annotations

from datetime import date, datetime

from lxml import etree

from app.edgar.parsers.dto import Filing13F, Holding13F, SecurityRef
from app.edgar.parsers.xmlutil import child, iter_named, text


def parse_period(primary_doc_xml: bytes) -> date | None:
    """Extract the reporting period (quarter-end) from primary_doc.xml."""
    try:
        root = etree.fromstring(primary_doc_xml)
    except etree.XMLSyntaxError:
        return None
    raw = text(root, "periodOfReport")
    return _parse_period_str(raw)


def _parse_period_str(raw: str | None) -> date | None:
    if not raw:
        return None
    for fmt in ("%m-%d-%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_information_table(
    xml: bytes, *, period: date | None = None, value_in_thousands: bool = False
) -> Filing13F:
    """Parse an information-table XML into holdings.

    ``value_in_thousands`` scales legacy values to whole USD.
    """
    root = etree.fromstring(xml)
    multiplier = 1000 if value_in_thousands else 1
    holdings: list[Holding13F] = []

    for it in iter_named(root, "infoTable"):
        cusip = (text(it, "cusip") or "").strip().upper()
        name = text(it, "nameOfIssuer") or ""
        if not cusip:
            continue

        raw_value = _to_int(text(it, "value"))
        shrs = child(it, "shrsOrPrnAmt")
        shares = _to_int(text(shrs, "sshPrnamt")) if shrs is not None else 0
        sh_type = (text(shrs, "sshPrnamtType") if shrs is not None else None) or "SH"

        voting = child(it, "votingAuthority")
        holdings.append(
            Holding13F(
                security=SecurityRef(cusip=cusip[:9], name=name),
                value=raw_value * multiplier,
                shares=shares,
                sh_prn_type=sh_type,
                put_call=text(it, "putCall"),
                investment_discretion=text(it, "investmentDiscretion"),
                voting_sole=_to_int(text(voting, "Sole")) if voting is not None else 0,
                voting_shared=_to_int(text(voting, "Shared")) if voting is not None else 0,
                voting_none=_to_int(text(voting, "None")) if voting is not None else 0,
            )
        )

    return Filing13F(period_of_report=period, holdings=holdings)


def _to_int(value: str | None) -> int:
    if not value:
        return 0
    cleaned = value.replace(",", "").replace("$", "").strip()
    try:
        return int(float(cleaned))
    except ValueError:
        return 0
