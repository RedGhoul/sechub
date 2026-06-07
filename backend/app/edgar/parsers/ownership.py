"""Parse Form 3/4/5 ownership documents (well-structured XML).

The ``ownershipDocument`` root carries the issuer, the reporting owner and
their relationship (director/officer/10%-owner), and non-derivative +
derivative transaction tables. We flatten both transaction tables into one list.
"""

from __future__ import annotations

from datetime import date, datetime

from lxml import etree

from app.edgar.common import format_cik
from app.edgar.parsers.dto import InsiderTransaction, OwnershipFiling, SecurityRef
from app.edgar.parsers.xmlutil import child, iter_named, text


def parse(xml: bytes) -> OwnershipFiling:
    root = etree.fromstring(xml)

    issuer_name = text(root, "issuerName") or ""
    ticker = (text(root, "issuerTradingSymbol") or "").strip().upper() or None
    # The ownership XML carries the issuer's CIK directly — an exact handle on
    # the company the insider trades in, used to join back to its filer entity.
    raw_cik = text(root, "issuerCik")
    issuer_cik = format_cik(raw_cik) if raw_cik else None
    issuer = SecurityRef(cusip="", name=issuer_name)
    # Stash the ticker on the ref via name-less channel: pipeline reads it below.
    issuer_ticker = ticker

    rel = next(iter_named(root, "reportingOwnerRelationship"), None)
    owner_name = text(root, "rptOwnerName") or ""

    filing = OwnershipFiling(
        issuer=issuer,
        insider_name=owner_name,
        insider_title=text(rel, "officerTitle") if rel is not None else None,
        is_director=_flag(text(rel, "isDirector")) if rel is not None else False,
        is_officer=_flag(text(rel, "isOfficer")) if rel is not None else False,
        is_ten_pct_owner=_flag(text(rel, "isTenPercentOwner")) if rel is not None else False,
        period_of_report=_parse_date(text(root, "periodOfReport")),
        issuer_cik=issuer_cik,
        transactions=[],
    )
    # Carry ticker out-of-band for the pipeline (SecurityRef has no ticker field).
    filing.issuer_ticker = issuer_ticker  # type: ignore[attr-defined]

    for txn in iter_named(root, "nonDerivativeTransaction"):
        filing.transactions.append(_parse_txn(txn, derivative=False))
    for txn in iter_named(root, "derivativeTransaction"):
        filing.transactions.append(_parse_txn(txn, derivative=True))

    return filing


def _parse_txn(txn: etree._Element, *, derivative: bool) -> InsiderTransaction:
    coding = child(txn, "transactionCoding")
    amounts = child(txn, "transactionAmounts")
    post = child(txn, "postTransactionAmounts")

    return InsiderTransaction(
        txn_date=_parse_date(_val(txn, "transactionDate")),
        txn_code=text(coding, "transactionCode") if coding is not None else None,
        is_derivative=derivative,
        security_title=_val(txn, "securityTitle"),
        shares=_to_float(_val(amounts, "transactionShares") if amounts is not None else None),
        price=_to_float(
            _val(amounts, "transactionPricePerShare") if amounts is not None else None
        ),
        acquired_disposed=(
            _val(amounts, "transactionAcquiredDisposedCode") if amounts is not None else None
        ),
        shares_owned_after=_to_float(
            _val(post, "sharesOwnedFollowingTransaction") if post is not None else None
        ),
    )


def _val(el: etree._Element | None, name: str) -> str | None:
    """Most Form 4 leaves wrap their content in a ``<value>`` child."""
    if el is None:
        return None
    node = child(el, name)
    if node is None:
        for n in iter_named(el, name):
            node = n
            break
    if node is None:
        return None
    v = child(node, "value")
    return (text(v) if v is not None else text(node)) or None


def _flag(value: str | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _to_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value.replace(",", "").replace("$", "").strip())
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
