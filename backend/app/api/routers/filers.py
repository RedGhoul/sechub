"""Filer endpoints: search, portfolio profile (current & historical), changes,
fund holdings, stakes held, and the issuer-side ('company') view."""

from __future__ import annotations

from datetime import date

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.serialize import FILER_COLS, SECURITY_COLS, filer_out, security_out
from app.db import get_connection
from app.edgar.common import format_cik
from app.schemas import (
    ChangesOut,
    FilerDetailOut,
    FilerOut,
    FundHoldingOut,
    HoldingChangeOut,
    HoldingOut,
    HolderOut,
    InsiderTxnOut,
    IssuerActivityOut,
    PeriodOut,
    SecurityOut,
    StakeOut,
)

router = APIRouter(prefix="/filers", tags=["filers"])


@router.get("", response_model=list[FilerOut])
def list_filers(
    q: str | None = Query(None, description="name substring"),
    kind: str | None = Query(None, description="institution|insider|fund"),
    limit: int = Query(50, ge=1, le=200),
    conn: psycopg.Connection = Depends(get_connection),
) -> list[dict]:
    sql = "SELECT * FROM filer"
    clauses: list[str] = []
    params: list = []
    if q:
        clauses.append("name ILIKE %s")
        params.append(f"%{q}%")
    if kind:
        clauses.append("kind = %s")
        params.append(kind)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY latest_filing_at DESC NULLS LAST LIMIT %s"
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def _resolve_filer(conn: psycopg.Connection, cik: str) -> dict:
    filer = conn.execute("SELECT * FROM filer WHERE cik = %s", (format_cik(cik),)).fetchone()
    if filer is None:
        raise HTTPException(404, "filer not found")
    return filer


def _latest_13f_period(conn: psycopg.Connection, filer_id: int) -> date | None:
    row = conn.execute(
        """SELECT period_of_report
             FROM filing
            WHERE filer_id = %s AND form_type LIKE '13F%%'
            ORDER BY period_of_report DESC NULLS LAST
            LIMIT 1""",
        (filer_id,),
    ).fetchone()
    return row["period_of_report"] if row else None


@router.get("/{cik}/periods", response_model=list[PeriodOut])
def filer_periods(cik: str, conn: psycopg.Connection = Depends(get_connection)) -> list[PeriodOut]:
    """Every 13F reporting period this filer has on record, newest first.

    Powers the historical quarter selector and a portfolio-value-over-time view.
    """
    filer = _resolve_filer(conn, cik)
    # Aggregate only the latest filing per period so a restatement amendment
    # (a second 13F under the same period) doesn't double the value/positions.
    rows = conn.execute(
        """WITH latest AS (
               SELECT DISTINCT ON (f.period_of_report) f.id
                 FROM filing f
                WHERE f.filer_id = %s AND f.form_type LIKE '13F%%'
                  AND f.period_of_report IS NOT NULL
                  AND EXISTS (SELECT 1 FROM holding hx WHERE hx.filing_id = f.id)
                ORDER BY f.period_of_report, f.filed_at DESC, f.id DESC
           )
           SELECT f.period_of_report AS period,
                  COALESCE(SUM(h.value), 0) AS total_value,
                  COUNT(h.id) AS position_count
             FROM filing f
             JOIN latest l ON l.id = f.id
             JOIN holding h ON h.filing_id = f.id
            GROUP BY f.period_of_report
            ORDER BY f.period_of_report DESC""",
        (filer["id"],),
    ).fetchall()
    return [
        PeriodOut(
            period=r["period"],
            total_value=int(r["total_value"]),
            position_count=r["position_count"],
        )
        for r in rows
        if r["period"] is not None
    ]


@router.get("/{cik}", response_model=FilerDetailOut)
def filer_detail(
    cik: str,
    period: date | None = Query(None, description="YYYY-MM-DD; defaults to latest"),
    conn: psycopg.Connection = Depends(get_connection),
) -> FilerDetailOut:
    """The filer's 13F portfolio for a period (latest by default), with each
    position's % of the portfolio."""
    filer = _resolve_filer(conn, cik)

    target_period = period or _latest_13f_period(conn, filer["id"])

    holdings: list[dict] = []
    if target_period is not None:
        holdings = conn.execute(
            f"""SELECT h.value, h.shares, h.sh_prn_type, h.put_call,
                       h.investment_discretion, h.voting_sole, h.voting_shared,
                       h.voting_none, {SECURITY_COLS}
                  FROM holding h
                  JOIN security s ON h.security_id = s.id
                 WHERE h.filing_id = (
                       SELECT f.id FROM filing f
                        WHERE f.filer_id = %s AND f.period_of_report = %s
                          AND EXISTS (SELECT 1 FROM holding hx WHERE hx.filing_id = f.id)
                        ORDER BY f.filed_at DESC, f.id DESC
                        LIMIT 1
                 )
                 ORDER BY h.value DESC""",
            (filer["id"], target_period),
        ).fetchall()

    total_value = sum(h["value"] for h in holdings)
    out_holdings = [
        HoldingOut(
            security=security_out(h),
            value=h["value"],
            shares=h["shares"],
            sh_prn_type=h["sh_prn_type"],
            put_call=h["put_call"],
            investment_discretion=h["investment_discretion"],
            voting_sole=h["voting_sole"],
            voting_shared=h["voting_shared"],
            voting_none=h["voting_none"],
            pct_of_portfolio=round(h["value"] / total_value * 100, 2) if total_value else None,
        )
        for h in holdings
    ]

    return FilerDetailOut(
        filer=FilerOut.model_validate(filer),
        period_of_report=target_period,
        total_value=total_value,
        position_count=len(holdings),
        holdings=out_holdings,
    )


@router.get("/{cik}/changes", response_model=ChangesOut)
def filer_changes(
    cik: str,
    period: date | None = Query(None, description="YYYY-MM-DD; defaults to latest"),
    conn: psycopg.Connection = Depends(get_connection),
) -> ChangesOut:
    """NEW / ADD / TRIM / EXIT positions for a quarter."""
    filer = _resolve_filer(conn, cik)

    target_period = period
    if target_period is None:
        row = conn.execute(
            """SELECT period FROM holding_change
                WHERE filer_id = %s ORDER BY period DESC LIMIT 1""",
            (filer["id"],),
        ).fetchone()
        target_period = row["period"] if row else None

    rows: list[dict] = []
    prev_period = None
    if target_period is not None:
        rows = conn.execute(
            f"""SELECT hc.action, hc.shares_delta, hc.value_delta, hc.pct_change,
                       hc.prev_period, {SECURITY_COLS}
                  FROM holding_change hc
                  JOIN security s ON hc.security_id = s.id
                 WHERE hc.filer_id = %s AND hc.period = %s
                 ORDER BY ABS(hc.value_delta) DESC""",
            (filer["id"], target_period),
        ).fetchall()
        prev_period = rows[0]["prev_period"] if rows else None

    return ChangesOut(
        filer=FilerOut.model_validate(filer),
        period=target_period,
        prev_period=prev_period,
        changes=[
            HoldingChangeOut(
                security=security_out(r),
                action=r["action"],
                shares_delta=r["shares_delta"],
                value_delta=r["value_delta"],
                pct_change=float(r["pct_change"]) if r["pct_change"] is not None else None,
            )
            for r in rows
        ],
    )


@router.get("/{cik}/fund-holdings", response_model=list[FundHoldingOut])
def filer_fund_holdings(
    cik: str,
    period: date | None = Query(None, description="YYYY-MM-DD; defaults to latest N-PORT"),
    limit: int = Query(500, ge=1, le=2000),
    conn: psycopg.Connection = Depends(get_connection),
) -> list[FundHoldingOut]:
    """A fund's NPORT-P portfolio for a period (latest by default)."""
    filer = _resolve_filer(conn, cik)

    target_period = period
    if target_period is None:
        row = conn.execute(
            """SELECT f.period_of_report
                 FROM filing f
                 JOIN fund_holding fh ON fh.filing_id = f.id
                WHERE f.filer_id = %s
                ORDER BY f.period_of_report DESC NULLS LAST
                LIMIT 1""",
            (filer["id"],),
        ).fetchone()
        target_period = row["period_of_report"] if row else None

    if target_period is None:
        return []

    rows = conn.execute(
        f"""SELECT fh.value, fh.balance, fh.pct_of_net_assets, {SECURITY_COLS}
              FROM fund_holding fh
              JOIN filing f ON fh.filing_id = f.id
              JOIN security s ON fh.security_id = s.id
             WHERE f.filer_id = %s AND f.period_of_report = %s
             ORDER BY fh.value DESC
             LIMIT %s""",
        (filer["id"], target_period, limit),
    ).fetchall()
    return [
        FundHoldingOut(
            security=security_out(r),
            value=r["value"],
            balance=float(r["balance"]) if r["balance"] is not None else None,
            pct_of_net_assets=float(r["pct_of_net_assets"])
            if r["pct_of_net_assets"] is not None
            else None,
        )
        for r in rows
    ]


@router.get("/{cik}/stakes-held", response_model=list[StakeOut])
def filer_stakes_held(
    cik: str,
    limit: int = Query(200, ge=1, le=500),
    conn: psycopg.Connection = Depends(get_connection),
) -> list[StakeOut]:
    """13D/13G beneficial-ownership stakes this filer holds in other companies."""
    filer = _resolve_filer(conn, cik)
    rows = conn.execute(
        f"""SELECT os.percent_of_class, os.shares, os.event_date, os.is_activist,
                   fl.form_type, {SECURITY_COLS}
              FROM ownership_stake os
              JOIN filing fl ON os.filing_id = fl.id
              JOIN security s ON os.security_id = s.id
             WHERE fl.filer_id = %s
             ORDER BY fl.filed_at DESC
             LIMIT %s""",
        (filer["id"], limit),
    ).fetchall()
    filer_model = FilerOut.model_validate(filer)
    return [
        StakeOut(
            filer=filer_model,
            security=security_out(r),
            form_type=r["form_type"],
            percent_of_class=float(r["percent_of_class"])
            if r["percent_of_class"] is not None
            else None,
            shares=r["shares"],
            event_date=r["event_date"],
            is_activist=r["is_activist"],
        )
        for r in rows
    ]


def _issuer_securities(conn: psycopg.Connection, filer: dict) -> list[dict]:
    """Securities that represent this filer's own company.

    A company shows up as a ``security`` only through *other* filers' documents
    about it (Form 4 insider trades, 13D/G stakes). Form 3/4/5 record the
    issuer's CIK, so we join on that exactly; for sources that don't (e.g.
    13D/G cover pages), we fall back to a best-effort name match.
    """
    # Escape LIKE metacharacters so a '%' or '_' in the company name can't act as
    # a wildcard (which would turn this into an unbounded / wrong-match scan).
    name_like = filer["name"].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return conn.execute(
        "SELECT * FROM security WHERE issuer_cik = %s OR name ILIKE %s",
        (filer["cik"], name_like),
    ).fetchall()


@router.get("/{cik}/issuer-activity", response_model=IssuerActivityOut)
def filer_issuer_activity(
    cik: str,
    limit: int = Query(100, ge=1, le=500),
    conn: psycopg.Connection = Depends(get_connection),
) -> IssuerActivityOut:
    """The 'company' side: insider trades, activist stakes, and institutional
    holders of this entity's *own* securities."""
    filer = _resolve_filer(conn, cik)
    securities = _issuer_securities(conn, filer)
    if not securities:
        return IssuerActivityOut(securities=[], insider_txns=[], stakes_in=[], top_holders=[])

    sec_ids = [s["id"] for s in securities]

    insider_rows = conn.execute(
        f"""SELECT it.insider_name, it.insider_title, it.is_director, it.is_officer,
                   it.is_ten_pct_owner, it.txn_date, it.txn_code, it.is_derivative,
                   it.security_title, it.shares, it.price, it.acquired_disposed,
                   it.shares_owned_after, {SECURITY_COLS}
              FROM insider_txn it
              JOIN security s ON it.security_id = s.id
             WHERE it.security_id = ANY(%s)
             ORDER BY it.txn_date DESC NULLS LAST
             LIMIT %s""",
        (sec_ids, limit),
    ).fetchall()
    insider_txns = [
        InsiderTxnOut(
            security=security_out(t),
            insider_name=t["insider_name"],
            insider_title=t["insider_title"],
            is_director=t["is_director"],
            is_officer=t["is_officer"],
            is_ten_pct_owner=t["is_ten_pct_owner"],
            txn_date=t["txn_date"],
            txn_code=t["txn_code"],
            is_derivative=t["is_derivative"],
            security_title=t["security_title"],
            shares=float(t["shares"]) if t["shares"] is not None else None,
            price=float(t["price"]) if t["price"] is not None else None,
            acquired_disposed=t["acquired_disposed"],
            shares_owned_after=float(t["shares_owned_after"])
            if t["shares_owned_after"] is not None
            else None,
        )
        for t in insider_rows
    ]

    stake_rows = conn.execute(
        f"""SELECT os.percent_of_class, os.shares, os.event_date, os.is_activist,
                   fl.form_type, {SECURITY_COLS}, {FILER_COLS}
              FROM ownership_stake os
              JOIN filing fl ON os.filing_id = fl.id
              JOIN filer fr ON fl.filer_id = fr.id
              JOIN security s ON os.security_id = s.id
             WHERE os.security_id = ANY(%s)
             ORDER BY fl.filed_at DESC
             LIMIT %s""",
        (sec_ids, limit),
    ).fetchall()
    stakes_in = [
        StakeOut(
            filer=filer_out(r),
            security=security_out(r),
            form_type=r["form_type"],
            percent_of_class=float(r["percent_of_class"])
            if r["percent_of_class"] is not None
            else None,
            shares=r["shares"],
            event_date=r["event_date"],
            is_activist=r["is_activist"],
        )
        for r in stake_rows
    ]

    # Top institutional holders: latest 13F position per filer for these
    # securities. DISTINCT ON dedupes to one row per filer in the DB (rather than
    # streaming every holding ever recorded into Python), then we take the top by
    # value.
    holder_rows = conn.execute(
        f"""SELECT * FROM (
                SELECT DISTINCT ON (fr.id)
                       h.shares, h.value, fl.period_of_report, {FILER_COLS}
                  FROM holding h
                  JOIN filing fl ON h.filing_id = fl.id
                  JOIN filer fr ON fl.filer_id = fr.id
                 WHERE h.security_id = ANY(%s)
                 ORDER BY fr.id, fl.period_of_report DESC NULLS LAST
            ) t
            ORDER BY value DESC
            LIMIT %s""",
        (sec_ids, limit),
    ).fetchall()
    top_holders = [
        HolderOut(
            filer=filer_out(r),
            shares=r["shares"],
            value=r["value"],
            period_of_report=r["period_of_report"],
        )
        for r in holder_rows
    ]

    return IssuerActivityOut(
        securities=[SecurityOut.model_validate(s) for s in securities],
        insider_txns=insider_txns,
        stakes_in=stakes_in,
        top_holders=top_holders,
    )
