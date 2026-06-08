"""Security endpoints: who holds a given stock."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, HTTPException

from app.api.serialize import FILER_COLS, filer_out
from app.db import get_connection
from app.schemas import HolderOut

router = APIRouter(prefix="/securities", tags=["securities"])


@router.get("/{cusip}/holders", response_model=list[HolderOut])
def holders(cusip: str, conn: psycopg.Connection = Depends(get_connection)) -> list[HolderOut]:
    """Institutions holding a security, by their latest reported position."""
    sec = conn.execute("SELECT id FROM security WHERE cusip = %s", (cusip.upper(),)).fetchone()
    if sec is None:
        raise HTTPException(404, "security not found")

    # Latest holding per filer for this security: ordered by filer then newest
    # period, we keep the first row seen per filer.
    rows = conn.execute(
        f"""SELECT h.shares, h.value, fl.period_of_report, {FILER_COLS}
              FROM holding h
              JOIN filing fl ON h.filing_id = fl.id
              JOIN filer fr ON fl.filer_id = fr.id
             WHERE h.security_id = %s
             ORDER BY fr.id, fl.period_of_report DESC NULLS LAST""",
        (sec["id"],),
    ).fetchall()

    seen: set[int] = set()
    out: list[HolderOut] = []
    for r in rows:
        if r["filer_id"] in seen:
            continue
        seen.add(r["filer_id"])
        out.append(
            HolderOut(
                filer=filer_out(r),
                shares=r["shares"],
                value=r["value"],
                period_of_report=r["period_of_report"],
            )
        )
    out.sort(key=lambda h: h.value, reverse=True)
    return out
