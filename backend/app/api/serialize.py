"""Helpers to build API response models from raw ``dict`` rows.

Joined queries alias the related entity's columns with a prefix (``sec_*``,
``filer_*``) so a single row carries several entities without key collisions.
These helpers pull a prefixed slice back out into a typed response model.
"""

from __future__ import annotations

from app.schemas import FilerOut, SecurityOut


def security_out(row: dict, prefix: str = "sec_") -> SecurityOut:
    return SecurityOut(
        id=row[f"{prefix}id"],
        cusip=row[f"{prefix}cusip"],
        name=row[f"{prefix}name"],
        ticker=row[f"{prefix}ticker"],
    )


def filer_out(row: dict, prefix: str = "filer_") -> FilerOut:
    return FilerOut(
        id=row[f"{prefix}id"],
        cik=row[f"{prefix}cik"],
        name=row[f"{prefix}name"],
        kind=row[f"{prefix}kind"],
        latest_filing_at=row[f"{prefix}latest_filing_at"],
    )


# Reusable SELECT fragments for the aliased columns the helpers above expect.
SECURITY_COLS = "s.id AS sec_id, s.cusip AS sec_cusip, s.name AS sec_name, s.ticker AS sec_ticker"
FILER_COLS = (
    "fr.id AS filer_id, fr.cik AS filer_cik, fr.name AS filer_name, "
    "fr.kind AS filer_kind, fr.latest_filing_at AS filer_latest_filing_at"
)
