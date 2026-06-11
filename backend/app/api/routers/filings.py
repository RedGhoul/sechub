"""Filing feed + detail, plus an on-demand ingest trigger."""

from __future__ import annotations

from datetime import date

import psycopg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.api.serialize import FILER_COLS, filer_out
from app.db import connect, get_connection
from app.edgar.feed import fetch_filer_history
from app.ingest.pipeline import ingest_filing
from app.schemas import FilingOut

router = APIRouter(prefix="/filings", tags=["filings"])

_FILING_COLS = (
    "fl.id, fl.accession_no, fl.form_type, fl.filed_at, fl.period_of_report, fl.source_url"
)


def _filing_out(row: dict) -> FilingOut:
    return FilingOut(
        id=row["id"],
        accession_no=row["accession_no"],
        form_type=row["form_type"],
        filed_at=row["filed_at"],
        period_of_report=row["period_of_report"],
        source_url=row["source_url"],
        filer=filer_out(row),
    )


@router.get("", response_model=list[FilingOut])
def feed(
    form: str | None = Query(None, description="exact form type, e.g. 13F-HR"),
    since: date | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    conn: psycopg.Connection = Depends(get_connection),
) -> list[FilingOut]:
    """Newest-first filing feed across all tracked forms."""
    sql = f"""SELECT {_FILING_COLS}, {FILER_COLS}
                FROM filing fl
                JOIN filer fr ON fl.filer_id = fr.id"""
    clauses: list[str] = []
    params: list = []
    if form:
        clauses.append("fl.form_type = %s")
        params.append(form)
    if since:
        clauses.append("fl.filed_at >= %s")
        params.append(since)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY fl.filed_at DESC, fl.id DESC LIMIT %s"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [_filing_out(r) for r in rows]


@router.get("/{filing_id}", response_model=FilingOut)
def filing_detail(filing_id: int, conn: psycopg.Connection = Depends(get_connection)) -> FilingOut:
    row = conn.execute(
        f"""SELECT {_FILING_COLS}, {FILER_COLS}
              FROM filing fl
              JOIN filer fr ON fl.filer_id = fr.id
             WHERE fl.id = %s""",
        (filing_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "filing not found")
    return _filing_out(row)


@router.post("/ingest/{cik}", status_code=202)
def trigger_ingest(
    cik: str,
    background: BackgroundTasks,
    forms: str = Query("13F-HR", description="comma-separated form types"),
    limit: int = Query(4, ge=1, le=40, description="max filings to pull"),
) -> dict:
    """Kick off ingestion of a filer's recent filings (runs in the background)."""
    wanted = {f.strip() for f in forms.split(",") if f.strip()}

    def _run() -> None:
        conn = connect()
        try:
            refs = fetch_filer_history(cik, forms=wanted)[:limit]
            for ref in refs:
                ingest_filing(conn, ref)
        finally:
            conn.close()

    background.add_task(_run)
    return {"status": "accepted", "cik": cik, "forms": sorted(wanted)}
