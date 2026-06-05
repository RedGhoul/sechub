"""Filing feed + detail, plus an on-demand ingest trigger."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db import SessionLocal, get_session
from app.edgar.feed import fetch_filer_history
from app.ingest.pipeline import ingest_filing
from app.models import Filing
from app.schemas import FilerOut, FilingOut

router = APIRouter(prefix="/filings", tags=["filings"])


@router.get("", response_model=list[FilingOut])
def feed(
    form: str | None = Query(None, description="exact form type, e.g. 13F-HR"),
    since: date | None = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_session),
) -> list[FilingOut]:
    """Newest-first filing feed across all tracked forms."""
    stmt = select(Filing).options(joinedload(Filing.filer))
    if form:
        stmt = stmt.where(Filing.form_type == form)
    if since:
        stmt = stmt.where(Filing.filed_at >= since)
    stmt = stmt.order_by(Filing.filed_at.desc(), Filing.id.desc()).limit(limit)
    rows = db.execute(stmt).scalars().all()
    return [
        FilingOut(
            id=f.id,
            accession_no=f.accession_no,
            form_type=f.form_type,
            filed_at=f.filed_at,
            period_of_report=f.period_of_report,
            source_url=f.source_url,
            filer=FilerOut.model_validate(f.filer),
        )
        for f in rows
    ]


@router.get("/{filing_id}", response_model=FilingOut)
def filing_detail(filing_id: int, db: Session = Depends(get_session)) -> FilingOut:
    f = db.execute(
        select(Filing).options(joinedload(Filing.filer)).where(Filing.id == filing_id)
    ).scalar_one_or_none()
    if f is None:
        raise HTTPException(404, "filing not found")
    return FilingOut(
        id=f.id,
        accession_no=f.accession_no,
        form_type=f.form_type,
        filed_at=f.filed_at,
        period_of_report=f.period_of_report,
        source_url=f.source_url,
        filer=FilerOut.model_validate(f.filer),
    )


@router.post("/ingest/{cik}", status_code=202)
def trigger_ingest(
    cik: str,
    background: BackgroundTasks,
    forms: str = Query("13F-HR", description="comma-separated form types"),
    limit: int = Query(4, le=40, description="max filings to pull"),
) -> dict:
    """Kick off ingestion of a filer's recent filings (runs in the background)."""
    wanted = {f.strip() for f in forms.split(",") if f.strip()}

    def _run() -> None:
        db = SessionLocal()
        try:
            refs = fetch_filer_history(cik, forms=wanted)[:limit]
            for ref in refs:
                ingest_filing(db, ref)
        finally:
            db.close()

    background.add_task(_run)
    return {"status": "accepted", "cik": cik, "forms": sorted(wanted)}
