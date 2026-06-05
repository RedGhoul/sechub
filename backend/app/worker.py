"""Background worker: poll the real-time feed and run the nightly backfill.

Run with ``python -m app.worker``. Uses APScheduler's blocking scheduler so it
can be the container's main process.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.db import SessionLocal
from app.edgar.feed import fetch_recent
from app.edgar.indexes import fetch_recent_days
from app.ingest.pipeline import ingest_filing

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("sechub.worker")


def poll_feed() -> None:
    """Pull the latest filings for each watched form type and ingest new ones."""
    db = SessionLocal()
    new_count = 0
    try:
        for form in settings.watch_forms:
            try:
                refs = fetch_recent(form, count=100)
            except Exception:
                log.exception("feed poll failed for %s", form)
                continue
            for ref in refs:
                if ingest_filing(db, ref) is not None:
                    new_count += 1
    finally:
        db.close()
    log.info("feed poll complete: %d new filings", new_count)


def nightly_backfill() -> None:
    """Backfill the last few days from the daily index to catch anything missed."""
    db = SessionLocal()
    new_count = 0
    try:
        refs = fetch_recent_days(set(settings.watch_forms), days=3)
        for ref in refs:
            if ingest_filing(db, ref) is not None:
                new_count += 1
    finally:
        db.close()
    log.info("nightly backfill complete: %d new filings", new_count)


def main() -> None:
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        poll_feed,
        "interval",
        seconds=settings.sechub_poll_interval,
        next_run_time=None,
        id="poll_feed",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        nightly_backfill,
        CronTrigger.from_crontab(settings.sechub_backfill_cron, timezone="UTC"),
        id="nightly_backfill",
        max_instances=1,
        coalesce=True,
    )
    log.info(
        "worker started: polling %s every %ss; backfill cron '%s'",
        settings.watch_forms,
        settings.sechub_poll_interval,
        settings.sechub_backfill_cron,
    )
    # Run one poll immediately on startup so there's data without waiting.
    poll_feed()
    scheduler.start()


if __name__ == "__main__":
    main()
