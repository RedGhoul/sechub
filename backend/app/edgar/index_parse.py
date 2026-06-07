"""Shared parser for EDGAR ``form.idx`` index files.

Both the *daily* index (``daily-index/.../form.YYYYMMDD.idx``) and the *quarterly
full* index (``full-index/{year}/QTR{n}/form.idx``) use the same form-sorted,
space-padded text layout. This module parses either into lightweight
``FilingRef``s so the daily poller and the historical backfill share one code
path.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from app.edgar.common import format_cik
from app.edgar.feed import FilingRef

_GUTTER = re.compile(r"\s{2,}")


def _split_idx_row(line: str) -> list[str]:
    # The form index pads columns with runs of 2+ spaces.
    return _GUTTER.split(line.strip())


def _accession_from_path(path: str) -> str:
    # edgar/data/1067983/0000950123-24-012345.txt
    name = path.rsplit("/", 1)[-1]
    return name.removesuffix(".txt")


def _parse_filed(value: str) -> date | None:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _wanted(form_type: str, forms: set[str]) -> bool:
    """Match a row's form type against the wanted set, tolerating amendments.

    ``forms`` holds base types (e.g. ``"SC 13D"``); a row like ``"SC 13D/A"``
    should still match, so we also test the part before the ``/A`` suffix.
    """
    if form_type in forms:
        return True
    return form_type.split("/", 1)[0].strip() in forms


def parse_form_index(text: str, forms: set[str], *, default_date: date | None = None) -> list[FilingRef]:
    """Parse a ``form.idx`` body into refs for the requested form types.

    Columns are: Form Type | Company Name | CIK | Date Filed | File Name. The
    file-date column is authoritative; ``default_date`` is only a fallback for
    malformed rows (and is what the daily index passes for its single day).
    """
    refs: list[FilingRef] = []
    in_body = False
    for line in text.splitlines():
        if line.startswith("---"):
            in_body = True
            continue
        if not in_body or not line.strip():
            continue
        cols = [c.strip() for c in _split_idx_row(line)]
        if len(cols) < 5:
            continue
        form_type, company, cik, filed, path = cols[0], cols[1], cols[2], cols[3], cols[4]
        if not _wanted(form_type, forms):
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
                filed_at=_parse_filed(filed) or default_date or date.today(),
            )
        )
    return refs
