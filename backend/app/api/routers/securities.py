"""Security endpoints: who holds a given stock."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.serialize import FILER_COLS, filer_out
from app.db import get_connection
from app.schemas import HolderOut, SecurityOut

router = APIRouter(prefix="/securities", tags=["securities"])


@router.get("/{cusip}", response_model=SecurityOut)
def security_detail(cusip: str, conn: psycopg.Connection = Depends(get_connection)) -> SecurityOut:
    """The security record (name, ticker) for a CUSIP."""
    row = conn.execute(
        "SELECT id, cusip, name, ticker FROM security WHERE cusip = %s",
        (cusip.upper(),),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "security not found")
    return SecurityOut.model_validate(row)


@router.get("/{cusip}/holders", response_model=list[HolderOut])
def holders(
    cusip: str,
    limit: int = Query(200, ge=1, le=1000),
    conn: psycopg.Connection = Depends(get_connection),
) -> list[HolderOut]:
    """Institutions holding a security, by their latest reported position."""
    sec = conn.execute("SELECT id FROM security WHERE cusip = %s", (cusip.upper(),)).fetchone()
    if sec is None:
        raise HTTPException(404, "security not found")

    # DISTINCT ON keeps the latest holding per filer in the DB (instead of
    # streaming every holding ever recorded for this security into Python), then
    # we return the top holders by value.
    rows = conn.execute(
        f"""SELECT * FROM (
                SELECT DISTINCT ON (fr.id)
                       h.shares, h.value, fl.period_of_report, {FILER_COLS}
                  FROM holding h
                  JOIN filing fl ON h.filing_id = fl.id
                  JOIN filer fr ON fl.filer_id = fr.id
                 WHERE h.security_id = %s
                 ORDER BY fr.id, fl.period_of_report DESC NULLS LAST
            ) t
            ORDER BY value DESC
            LIMIT %s""",
        (sec["id"], limit),
    ).fetchall()

    return [
        HolderOut(
            filer=filer_out(r),
            shares=r["shares"],
            value=r["value"],
            period_of_report=r["period_of_report"],
        )
        for r in rows
    ]
