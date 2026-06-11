"""Backfill discovery via EDGAR daily index files.

The daily index (``daily-index/{year}/QTR{n}/form.{yyyymmdd}.idx``) lists every
filing accepted on a given day, grouped by form type. We use it to backfill the
last N days of a set of form types into the ingest pipeline. The historical
(multi-year) equivalent lives in :mod:`app.edgar.full_index`.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import httpx

from app.edgar.client import edgar_client
from app.edgar.common import ARCHIVES
from app.edgar.feed import FilingRef
from app.edgar.index_parse import parse_form_index

log = logging.getLogger("sechub.indexes")


def _quarter(d: date) -> int:
    return (d.month - 1) // 3 + 1


def daily_index_url(d: date) -> str:
    return f"{ARCHIVES}/daily-index/{d.year}/QTR{_quarter(d)}/form.{d:%Y%m%d}.idx"


def fetch_day(d: date, forms: set[str]) -> list[FilingRef]:
    """Return filing refs of the requested form types accepted on day ``d``.

    A 404 means there's no index for that day (weekend/holiday) — genuinely
    empty. Other failures propagate so the caller can tell "no filings" apart
    from "couldn't fetch"."""
    try:
        text = edgar_client.get_text(daily_index_url(d))
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return []
        raise
    return parse_form_index(text, forms, default_date=d)


def fetch_recent_days(forms: set[str], days: int = 3) -> list[FilingRef]:
    """Backfill the last ``days`` calendar days for the given form types.

    One day failing to fetch is logged and skipped rather than aborting the
    whole window; the worker re-covers this rolling window every cycle."""
    today = date.today()
    out: list[FilingRef] = []
    for offset in range(days):
        d = today - timedelta(days=offset)
        try:
            out.extend(fetch_day(d, forms))
        except Exception:
            log.exception("daily index fetch failed for %s; skipping", d)
    return out
