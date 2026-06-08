"""The ingest pipeline: discovered filing ref -> parsed, persisted rows.

``ingest_filing`` is idempotent on accession number and dispatches to a
per-form handler. Handlers fetch only the documents they need (via
``edgar.locate``), parse them offline-style, and insert child rows referencing
the ``filing``.
"""

from __future__ import annotations

import logging
from datetime import date

import psycopg

from app.edgar import header, locate
from app.edgar.client import edgar_client
from app.edgar.common import filing_dir_url
from app.edgar.feed import FilingRef
from app.edgar.parsers import form13f, nport, ownership, schedule13dg
from app.ingest.diff import compute_changes
from app.ingest.resolve import get_or_create_filer, get_or_create_security

log = logging.getLogger("sechub.ingest")

# 13F amendment compliance: filings before this report value in thousands.
_DOLLARS_SINCE = date(2023, 1, 3)


def already_ingested(conn: psycopg.Connection, accession: str) -> bool:
    return (
        conn.execute("SELECT 1 FROM filing WHERE accession_no = %s", (accession,)).fetchone()
        is not None
    )


def ingest_filing(conn: psycopg.Connection, ref: FilingRef) -> dict | None:
    """Fetch, parse, and persist one filing. Returns the filing row, or None if
    it was already ingested or its form type is unsupported."""
    if already_ingested(conn, ref.accession_no):
        return None

    family = _family(ref.form_type)
    if family is None:
        return None

    filer = get_or_create_filer(conn, ref.cik, ref.filer_name, kind=_KIND[family])
    source_url = f"{filing_dir_url(ref.cik, ref.accession_no)}/{ref.accession_no}-index.htm"
    filing = conn.execute(
        """INSERT INTO filing (accession_no, filer_id, form_type, filed_at, source_url)
           VALUES (%s, %s, %s, %s, %s) RETURNING *""",
        (ref.accession_no, filer["id"], ref.form_type, ref.filed_at, source_url),
    ).fetchone()

    try:
        period = _HANDLERS[family](conn, filing, ref)
    except Exception:  # one bad filing shouldn't poison the batch
        log.exception("failed to parse %s (%s)", ref.accession_no, ref.form_type)
        conn.rollback()
        return None

    conn.execute("UPDATE filing SET period_of_report = %s WHERE id = %s", (period, filing["id"]))
    conn.execute(
        "UPDATE filer SET latest_filing_at = %s WHERE id = %s",
        (ref.filed_at, filer["id"]),
    )
    if family == "13F" and period:
        compute_changes(conn, filer["id"], period)

    conn.commit()
    filing["period_of_report"] = period
    log.info("ingested %s %s for %s", ref.form_type, ref.accession_no, filer["name"])
    return filing


# --- per-form handlers: insert child rows, return period_of_report ----------


def _handle_13f(conn: psycopg.Connection, filing: dict, ref: FilingRef) -> date | None:
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
        sec = get_or_create_security(conn, h.security)
        conn.execute(
            """INSERT INTO holding
               (filing_id, security_id, value, shares, sh_prn_type, put_call,
                investment_discretion, voting_sole, voting_shared, voting_none)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                filing["id"],
                sec["id"],
                h.value,
                h.shares,
                h.sh_prn_type,
                h.put_call,
                h.investment_discretion,
                h.voting_sole,
                h.voting_shared,
                h.voting_none,
            ),
        )
    return parsed.period_of_report or period


def _handle_ownership(conn: psycopg.Connection, filing: dict, ref: FilingRef) -> date | None:
    xml_url = locate.find_ownership_xml(ref.cik, ref.accession_no)
    if not xml_url:
        return None
    parsed = ownership.parse(edgar_client.get_bytes(xml_url))
    ticker = getattr(parsed, "issuer_ticker", None)
    sec = get_or_create_security(conn, parsed.issuer, ticker=ticker, issuer_cik=parsed.issuer_cik)
    for t in parsed.transactions:
        conn.execute(
            """INSERT INTO insider_txn
               (filing_id, security_id, insider_name, insider_title, is_director,
                is_officer, is_ten_pct_owner, txn_date, txn_code, is_derivative,
                security_title, shares, price, acquired_disposed, shares_owned_after)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                filing["id"],
                sec["id"],
                parsed.insider_name,
                parsed.insider_title,
                parsed.is_director,
                parsed.is_officer,
                parsed.is_ten_pct_owner,
                t.txn_date,
                t.txn_code,
                t.is_derivative,
                t.security_title,
                t.shares,
                t.price,
                t.acquired_disposed,
                t.shares_owned_after,
            ),
        )
    return parsed.period_of_report


def _handle_stake(conn: psycopg.Connection, filing: dict, ref: FilingRef) -> date | None:
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
    sec = get_or_create_security(conn, parsed.issuer, issuer_cik=subject_cik)
    conn.execute(
        """INSERT INTO ownership_stake
           (filing_id, security_id, percent_of_class, shares, event_date, is_activist)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (
            filing["id"],
            sec["id"],
            parsed.percent_of_class,
            parsed.shares,
            parsed.event_date,
            parsed.is_activist,
        ),
    )
    return parsed.event_date


def _handle_nport(conn: psycopg.Connection, filing: dict, ref: FilingRef) -> date | None:
    primary = locate.find_primary_doc(ref.cik, ref.accession_no)
    if not primary:
        return None
    parsed = nport.parse(edgar_client.get_bytes(primary))
    for h in parsed.holdings:
        sec = get_or_create_security(conn, h.security)
        conn.execute(
            """INSERT INTO fund_holding
               (filing_id, security_id, value, balance, pct_of_net_assets)
               VALUES (%s, %s, %s, %s, %s)""",
            (filing["id"], sec["id"], h.value, h.balance, h.pct_of_net_assets),
        )
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
