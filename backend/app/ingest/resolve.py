"""Get-or-create helpers for the shared Filer and Security entities.

Centralized so every parser/pipeline path dedupes identically. Securities are
keyed by the best identifier available (CUSIP > ticker > issuer CIK).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.edgar.parsers.dto import SecurityRef
from app.models import Filer, Security


def get_or_create_filer(db: Session, cik: str, name: str, kind: str = "institution") -> Filer:
    filer = db.execute(select(Filer).where(Filer.cik == cik)).scalar_one_or_none()
    if filer is None:
        filer = Filer(cik=cik, name=name or cik, kind=kind)
        db.add(filer)
        db.flush()
    elif name and filer.name != name:
        filer.name = name
    return filer


def _security_key(ref: SecurityRef, ticker: str | None, issuer_cik: str | None) -> str:
    if ref.cusip:
        return ref.cusip
    if ticker:
        return f"TICKER:{ticker}"
    if issuer_cik:
        return f"CIK:{issuer_cik}"
    # Last resort: name-based, so distinct unnamed issuers don't collapse.
    return f"NAME:{ref.name[:24]}"


def get_or_create_security(
    db: Session,
    ref: SecurityRef,
    *,
    ticker: str | None = None,
    issuer_cik: str | None = None,
) -> Security:
    key = _security_key(ref, ticker, issuer_cik)
    sec = db.execute(select(Security).where(Security.key == key)).scalar_one_or_none()
    if sec is None:
        sec = Security(
            key=key,
            cusip=ref.cusip or None,
            name=ref.name or key,
            ticker=ticker,
        )
        db.add(sec)
        db.flush()
        return sec
    # Enrich a thin existing row when a richer filing arrives.
    if ticker and not sec.ticker:
        sec.ticker = ticker
    if ref.cusip and not sec.cusip:
        sec.cusip = ref.cusip
    if ref.name and (not sec.name or sec.name == key):
        sec.name = ref.name
    return sec
