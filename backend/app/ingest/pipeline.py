"""The ingest pipeline: discovered filing ref -> parsed, persisted rows.

``ingest_filing`` is idempotent on accession number and dispatches to a
per-form handler. Handlers fetch only the documents they need (via
``edgar.locate``), parse them offline-style, and attach child rows to the
``Filing``.
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.edgar import header, locate
from app.edgar.client import edgar_client
from app.edgar.common import filing_dir_url
from app.edgar.feed import FilingRef
from app.edgar.parsers import form13f, nport, ownership, schedule13dg
from app.ingest.diff import compute_changes
from app.ingest.resolve import get_or_create_filer, get_or_create_security
from app.models import (
    Filing,
    FundHolding,
    Holding,
    InsiderTxn,
    OwnershipStake,
)

log = logging.getLogger("sechub.ingest")

# 13F amendment compliance: filings before this report value in thousands.
_DOLLARS_SINCE = date(2023, 1, 3)


def already_ingested(db: Session, accession: str) -> bool:
    return (
        db.execute(select(Filing.id).where(Filing.accession_no == accession)).first()
        is not None
    )


def ingest_filing(db: Session, ref: FilingRef) -> Filing | None:
    """Fetch, parse, and persist one filing. Returns the Filing, or None if
    it was already ingested or its form type is unsupported."""
    if already_ingested(db, ref.accession_no):
        return None

    family = _family(ref.form_type)
    if family is None:
        return None

    filer = get_or_create_filer(db, ref.cik, ref.filer_name, kind=_KIND[family])
    filing = Filing(
        accession_no=ref.accession_no,
        filer_id=filer.id,
        form_type=ref.form_type,
        filed_at=ref.filed_at,
        source_url=f"{filing_dir_url(ref.cik, ref.accession_no)}/"
        f"{ref.accession_no}-index.htm",
    )
    db.add(filing)
    db.flush()

    try:
        period = _HANDLERS[family](db, filing, ref)
    except Exception:  # one bad filing shouldn't poison the batch
        log.exception("failed to parse %s (%s)", ref.accession_no, ref.form_type)
        db.rollback()
        return None

    filing.period_of_report = period
    filer.latest_filing_at = ref.filed_at
    # Persist the period before diffing: the session is autoflush=False, so the
    # change-detection query would otherwise not see this filing's period yet.
    db.flush()
    if family == "13F" and period:
        compute_changes(db, filer.id, period)

    db.commit()
    log.info("ingested %s %s for %s", ref.form_type, ref.accession_no, filer.name)
    return filing


# --- per-form handlers: add child rows, return period_of_report ------------


def _handle_13f(db: Session, filing: Filing, ref: FilingRef) -> date | None:
    primary = locate.find_primary_doc(ref.cik, ref.accession_no)
    period = form13f.parse_period(edgar_client.get_bytes(primary)) if primary else None

    table_url = locate.find_information_table(ref.cik, ref.accession_no)
    if not table_url:
        return period
    in_thousands = ref.filed_at < _DOLLARS_SINCE
    parsed = form13f.parse_information_table(
        edgar_client.get_bytes(table_url),
        period=period,
        value_in_thousands=in_thousands,
    )
    for h in parsed.holdings:
        sec = get_or_create_security(db, h.security)
        db.add(
            Holding(
                filing_id=filing.id,
                security_id=sec.id,
                value=h.value,
                shares=h.shares,
                sh_prn_type=h.sh_prn_type,
                put_call=h.put_call,
                investment_discretion=h.investment_discretion,
                voting_sole=h.voting_sole,
                voting_shared=h.voting_shared,
                voting_none=h.voting_none,
            )
        )
    db.flush()
    return parsed.period_of_report or period


def _handle_ownership(db: Session, filing: Filing, ref: FilingRef) -> date | None:
    xml_url = locate.find_ownership_xml(ref.cik, ref.accession_no)
    if not xml_url:
        return None
    parsed = ownership.parse(edgar_client.get_bytes(xml_url))
    ticker = getattr(parsed, "issuer_ticker", None)
    sec = get_or_create_security(db, parsed.issuer, ticker=ticker, issuer_cik=parsed.issuer_cik)
    for t in parsed.transactions:
        db.add(
            InsiderTxn(
                filing_id=filing.id,
                security_id=sec.id,
                insider_name=parsed.insider_name,
                insider_title=parsed.insider_title,
                is_director=parsed.is_director,
                is_officer=parsed.is_officer,
                is_ten_pct_owner=parsed.is_ten_pct_owner,
                txn_date=t.txn_date,
                txn_code=t.txn_code,
                is_derivative=t.is_derivative,
                security_title=t.security_title,
                shares=t.shares,
                price=t.price,
                acquired_disposed=t.acquired_disposed,
                shares_owned_after=t.shares_owned_after,
            )
        )
    db.flush()
    return parsed.period_of_report


def _handle_stake(db: Session, filing: Filing, ref: FilingRef) -> date | None:
    html_url = locate.find_primary_html(ref.cik, ref.accession_no)
    if not html_url:
        return None
    parsed = schedule13dg.parse(
        edgar_client.get_bytes(html_url),
        form_type=ref.form_type,
        issuer_hint=ref.filer_name,
    )
    # The cover page has no issuer CIK; recover it from the filing's SGML header
    # so the stake joins to its issuer exactly (falls back to CUSIP/name).
    subject_cik = header.fetch_subject_cik(ref.cik, ref.accession_no)
    sec = get_or_create_security(db, parsed.issuer, issuer_cik=subject_cik)
    db.add(
        OwnershipStake(
            filing_id=filing.id,
            security_id=sec.id,
            percent_of_class=parsed.percent_of_class,
            shares=parsed.shares,
            event_date=parsed.event_date,
            is_activist=parsed.is_activist,
        )
    )
    db.flush()
    return parsed.event_date


def _handle_nport(db: Session, filing: Filing, ref: FilingRef) -> date | None:
    primary = locate.find_primary_doc(ref.cik, ref.accession_no)
    if not primary:
        return None
    parsed = nport.parse(edgar_client.get_bytes(primary))
    for h in parsed.holdings:
        sec = get_or_create_security(db, h.security)
        db.add(
            FundHolding(
                filing_id=filing.id,
                security_id=sec.id,
                value=h.value,
                balance=h.balance,
                pct_of_net_assets=h.pct_of_net_assets,
            )
        )
    db.flush()
    return parsed.period_of_report


_HANDLERS = {
    "13F": _handle_13f,
    "OWNERSHIP": _handle_ownership,
    "STAKE": _handle_stake,
    "NPORT": _handle_nport,
}
_KIND = {
    "13F": "institution",
    "OWNERSHIP": "insider",
    "STAKE": "institution",
    "NPORT": "fund",
}


def _family(form_type: str) -> str | None:
    """Map a raw EDGAR form type (incl. amendments) to a handler family."""
    ft = form_type.upper().strip()
    base = ft.split("/")[0].strip()  # drop "/A" amendment suffix
    if base.startswith("13F"):
        return "13F"
    if base in {"3", "4", "5"}:
        return "OWNERSHIP"
    if base.startswith("SC 13D") or base.startswith("SC 13G") or base in {"13D", "13G"}:
        return "STAKE"
    if base.startswith("NPORT"):
        return "NPORT"
    return None
