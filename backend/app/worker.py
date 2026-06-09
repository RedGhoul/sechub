"""Continuous scraper worker: poll the EDGAR feed and run a daily catch-up.

Run with ``python -m app.worker``. This is a plain blocking loop designed to be
a container's main process — no scheduler framework. Each cycle it polls the
real-time feed, and once per UTC day (on or after ``SECHUB_BACKFILL_HOUR``) it
also backfills the last few days from the daily index to catch anything the
poller missed, then sleeps for ``SECHUB_POLL_INTERVAL`` seconds.

Operational/DB notes:

* It traps SIGINT/SIGTERM and stops at the end of the current cycle, so
  ``docker stop`` shuts it down cleanly within the grace period instead of
  being killed mid-write.
* Every cycle uses a fresh, context-managed connection (``with connect()``),
  which commits/rolls back and closes on exit. A transient DB blip or restart
  therefore costs at most one cycle rather than wedging a long-lived
  connection. ``ingest_filing`` owns the per-filing transaction, so one bad
  filing never aborts the rest of the cycle.
"""

from __future__ import annotations

import logging
import signal
import threading
import time
from datetime import date, datetime, timezone
from types import FrameType

from app.config import settings
from app.db import connect
from app.edgar.feed import fetch_recent
from app.edgar.indexes import fetch_recent_days
from app.ingest.pipeline import ingest_filing

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("sechub.worker")

# Set by SIGINT/SIGTERM. Also drives an interruptible sleep so the loop reacts
# to `docker stop` promptly instead of after a full poll interval.
_shutdown = threading.Event()


def poll_feed() -> int:
    """Pull the latest filings for each watched form and ingest the new ones.

    One connection serves the whole cycle and is closed by the context manager;
    ``ingest_filing`` commits/rolls back per filing. Returns the number of newly
    ingested filings.
    """
    new_count = 0
    with connect() as conn:
        for form in settings.watch_forms:
            try:
                refs = fetch_recent(form, count=100)
            except Exception:
                log.exception("feed poll failed for %s", form)
                continue
            for ref in refs:
                if ingest_filing(conn, ref) is not None:
                    new_count += 1
    log.info("feed poll complete: %d new filings", new_count)
    return new_count


def daily_backfill() -> int:
    """Backfill the last few days from the daily index to catch missed filings."""
    new_count = 0
    with connect() as conn:
        try:
            refs = fetch_recent_days(set(settings.watch_forms), days=3)
        except Exception:
            log.exception("daily-index backfill failed")
            return 0
        for ref in refs:
            if ingest_filing(conn, ref) is not None:
                new_count += 1
    log.info("daily backfill complete: %d new filings", new_count)
    return new_count


def _install_signal_handlers() -> None:
    def _request_stop(signum: int, _frame: FrameType | None) -> None:
        log.info("received %s; stopping after the current cycle", signal.Signals(signum).name)
        _shutdown.set()

    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)


def _backfill_due(last_run: date | None, now: datetime) -> bool:
    """True at most once per UTC day, on/after the configured backfill hour.

    A process restart resets the in-memory ``last_run``, so a restart after the
    hour re-runs the catch-up — harmless, since ingestion is idempotent.
    """
    return now.hour >= settings.sechub_backfill_hour and last_run != now.date()


def run_forever() -> None:
    """Poll → (maybe) daily backfill → sleep, until a stop signal arrives."""
    _install_signal_handlers()
    log.info(
        "worker started: polling %s every %ss; daily backfill on/after %02d:00 UTC",
        settings.watch_forms,
        settings.sechub_poll_interval,
        settings.sechub_backfill_hour,
    )
    last_backfill: date | None = None
    while not _shutdown.is_set():
        started = time.monotonic()
        try:
            poll_feed()
            now = datetime.now(tz=timezone.utc)
            if _backfill_due(last_backfill, now):
                daily_backfill()
                last_backfill = now.date()
        except Exception:
            # Never let a transient failure kill the loop; log and retry next cycle.
            log.exception("poll cycle failed; continuing")
        # Interruptible sleep for the remainder of the interval.
        elapsed = time.monotonic() - started
        _shutdown.wait(timeout=max(0.0, settings.sechub_poll_interval - elapsed))
    log.info("worker stopped cleanly")


def main() -> None:
    run_forever()


if __name__ == "__main__":
    main()
