"""Historical backfill: ingest the full history of the watched form types.

Walks EDGAR's quarterly full-index from ``--since-year`` to today, feeding every
matching filing through the (idempotent) ingest pipeline. Progress is tracked
per quarter in ``backfill_progress`` so the job can be stopped and resumed.

Run with::

    python -m app.backfill                       # since the configured year
    python -m app.backfill --since-year 1993     # the full EDGAR archive
    python -m app.backfill --forms "13F-HR,4"    # a subset of forms

This is a large, long-running job: a quarter of Form 4 filings alone is hundreds
of thousands of submissions, each requiring document fetches throttled to the
SEC rate limit. It is meant to run as a one-off batch process, not on the poll
loop, and is safe to interrupt — re-running resumes where it left off.
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.edgar import full_index
from app.ingest.pipeline import ingest_filing
from app.models import BackfillProgress

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("sechub.backfill")

# Persist the running ingest count this often so progress survives a crash.
_CHECKPOINT_EVERY = 100


def _segment(db: Session, year: int, quarter: int) -> BackfillProgress:
    seg = db.execute(
        select(BackfillProgress).where(
            BackfillProgress.year == year, BackfillProgress.quarter == quarter
        )
    ).scalar_one_or_none()
    if seg is None:
        seg = BackfillProgress(year=year, quarter=quarter)
        db.add(seg)
        db.flush()
    return seg


def backfill_quarter(db: Session, year: int, quarter: int, forms: set[str]) -> int:
    """Ingest one quarter's full index. Returns the number of new filings."""
    seg = _segment(db, year, quarter)
    if seg.completed_at is not None:
        log.info("skip %dQ%d (already complete)", year, quarter)
        return 0

    refs = full_index.fetch_quarter(year, quarter, forms)
    seg.forms = ",".join(sorted(forms))
    seg.filings_seen = len(refs)
    db.commit()
    log.info("%dQ%d: %d candidate filings", year, quarter, len(refs))

    ingested = 0
    for ref in refs:
        if ingest_filing(db, ref) is not None:
            ingested += 1
            if ingested % _CHECKPOINT_EVERY == 0:
                seg.filings_ingested = ingested
                db.commit()
                log.info("%dQ%d: %d ingested so far", year, quarter, ingested)

    seg.filings_ingested = ingested
    seg.completed_at = datetime.now(tz=timezone.utc)
    db.commit()
    log.info("%dQ%d done: %d new filings", year, quarter, ingested)
    return ingested


def run_backfill(since_year: int, forms: set[str]) -> None:
    db = SessionLocal()
    total = 0
    try:
        for year, quarter in full_index.quarters_in_range(since_year):
            total += backfill_quarter(db, year, quarter, forms)
    finally:
        db.close()
    log.info("backfill complete: %d new filings total", total)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill SEC filing history from EDGAR full-index.")
    parser.add_argument(
        "--since-year",
        type=int,
        default=settings.sechub_backfill_since_year,
        help="earliest year to backfill (EDGAR starts at 1993)",
    )
    parser.add_argument(
        "--forms",
        type=str,
        default=settings.sechub_watch_forms,
        help="comma-separated base form types to backfill",
    )
    args = parser.parse_args()
    forms = {f.strip() for f in args.forms.split(",") if f.strip()}
    log.info("starting backfill from %d for forms %s", args.since_year, sorted(forms))
    run_backfill(args.since_year, forms)


if __name__ == "__main__":
    main()
