"""Historical discovery via EDGAR quarterly *full-index* files.

``full-index/{year}/QTR{n}/form.idx`` enumerates **every** filing accepted in a
quarter, for every filer, back to 1993 Q1. Walking these is how SecHub backfills
the complete history of the watched form types for every entity that has ever
filed one — far beyond the few-day window the daily poller covers.
"""

from __future__ import annotations

from datetime import date

import httpx

from app.edgar.client import edgar_client
from app.edgar.common import ARCHIVES
from app.edgar.feed import FilingRef
from app.edgar.index_parse import parse_form_index

# EDGAR's full-index coverage begins here.
EDGAR_EPOCH_YEAR = 1993


def full_index_url(year: int, quarter: int) -> str:
    return f"{ARCHIVES}/full-index/{year}/QTR{quarter}/form.idx"


def fetch_quarter(year: int, quarter: int, forms: set[str]) -> list[FilingRef]:
    """All filings of the requested form types accepted in ``year`` ``QTR{n}``.

    Returns an empty list for quarters with no published index (e.g. a future
    quarter), so callers can iterate a range without special-casing the edges.
    A transient failure (network/5xx surviving the client's retries) is *not*
    swallowed — it propagates so the backfill leaves the quarter incomplete and
    retries it, rather than recording it as an empty, completed segment.
    """
    try:
        text = edgar_client.get_text(full_index_url(year, quarter))
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return []
        raise
    # The quarterly index carries a per-row Date Filed column we trust; the
    # quarter's first day is only a fallback for malformed rows.
    return parse_form_index(text, forms, default_date=date(year, (quarter - 1) * 3 + 1, 1))


def quarters_in_range(since_year: int, until: date | None = None) -> list[tuple[int, int]]:
    """``(year, quarter)`` pairs from ``since_year`` Q1 through ``until`` (incl).

    Clamped to EDGAR's epoch and to the quarter containing ``until`` (default:
    today), so the backfill never asks for indexes that cannot exist.
    """
    until = until or date.today()
    start = max(since_year, EDGAR_EPOCH_YEAR)
    out: list[tuple[int, int]] = []
    for year in range(start, until.year + 1):
        for quarter in range(1, 5):
            if year == until.year and (quarter - 1) * 3 + 1 > until.month:
                break
            out.append((year, quarter))
    return out
