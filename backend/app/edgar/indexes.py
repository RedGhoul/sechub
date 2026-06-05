"""Backfill discovery via EDGAR daily index files.

The daily index (``daily-index/{year}/QTR{n}/form.{yyyymmdd}.idx``) lists every
filing accepted on a given day, grouped by form type. We use it to backfill the
last N days of a set of form types into the ingest pipeline. The historical
(multi-year) equivalent lives in :mod:`app.edgar.full_index`.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.edgar.client import edgar_client
from app.edgar.common import ARCHIVES
from app.edgar.feed import FilingRef
from app.edgar.index_parse import parse_form_index


def _quarter(d: date) -> int:
    return (d.month - 1) // 3 + 1


def daily_index_url(d: date) -> str:
    return f"{ARCHIVES}/daily-index/{d.year}/QTR{_quarter(d)}/form.{d:%Y%m%d}.idx"


def fetch_day(d: date, forms: set[str]) -> list[FilingRef]:
    """Return filing refs of the requested form types accepted on day ``d``."""
    try:
        text = edgar_client.get_text(daily_index_url(d))
    except Exception:
        # Weekends/holidays have no index; treat as empty.
        return []
    return parse_form_index(text, forms, default_date=d)


def fetch_recent_days(forms: set[str], days: int = 3) -> list[FilingRef]:
    """Backfill the last ``days`` calendar days for the given form types."""
    today = date.today()
    out: list[FilingRef] = []
    for offset in range(days):
        out.extend(fetch_day(today - timedelta(days=offset), forms))
    return out
