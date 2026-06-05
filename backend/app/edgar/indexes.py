"""Backfill discovery via EDGAR daily/full index files.

The daily index (``daily-index/{year}/QTR{n}/form.{yyyymmdd}.idx``) lists every
filing accepted on a given day, grouped by form type. We use it to backfill the
last N days of a set of form types into the ingest pipeline.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.edgar.client import edgar_client
from app.edgar.common import ARCHIVES, format_cik
from app.edgar.feed import FilingRef


def _quarter(d: date) -> int:
    return (d.month - 1) // 3 + 1


def daily_index_url(d: date) -> str:
    return f"{ARCHIVES}/daily-index/{d.year}/QTR{_quarter(d)}/form.{d:%Y%m%d}.idx"


def fetch_day(d: date, forms: set[str]) -> list[FilingRef]:
    """Return filing refs of the requested form types accepted on day ``d``.

    The ``.idx`` is a fixed-ish column text file with a header; the form-sorted
    variant starts each data row with the form type. We split on the
    multi-space gutters which is robust to the column padding.
    """
    try:
        text = edgar_client.get_text(daily_index_url(d))
    except Exception:
        # Weekends/holidays have no index; treat as empty.
        return []

    refs: list[FilingRef] = []
    in_body = False
    for line in text.splitlines():
        if line.startswith("---"):
            in_body = True
            continue
        if not in_body or not line.strip():
            continue
        # Columns: Form Type | Company Name | CIK | Date Filed | File Name
        cols = [c.strip() for c in _split_idx_row(line)]
        if len(cols) < 5:
            continue
        form_type, company, cik, _filed, path = cols[0], cols[1], cols[2], cols[3], cols[4]
        if form_type not in forms:
            continue
        accession = _accession_from_path(path)
        if not accession:
            continue
        refs.append(
            FilingRef(
                cik=format_cik(cik),
                filer_name=company,
                accession_no=accession,
                form_type=form_type,
                filed_at=d,
            )
        )
    return refs


def fetch_recent_days(forms: set[str], days: int = 3) -> list[FilingRef]:
    """Backfill the last ``days`` calendar days for the given form types."""
    today = date.today()
    out: list[FilingRef] = []
    for offset in range(days):
        out.extend(fetch_day(today - timedelta(days=offset), forms))
    return out


def _split_idx_row(line: str) -> list[str]:
    # The form index pads columns with runs of 2+ spaces.
    import re

    return re.split(r"\s{2,}", line.strip())


def _accession_from_path(path: str) -> str:
    # edgar/data/1067983/0000950123-24-012345.txt
    name = path.rsplit("/", 1)[-1]
    return name.removesuffix(".txt")
