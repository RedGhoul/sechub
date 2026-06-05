"""Security endpoints: who holds a given stock."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Filer, Filing, Holding, Security
from app.schemas import FilerOut, HolderOut

router = APIRouter(prefix="/securities", tags=["securities"])


@router.get("/{cusip}/holders", response_model=list[HolderOut])
def holders(cusip: str, db: Session = Depends(get_session)) -> list[HolderOut]:
    """Institutions holding a security, by their latest reported position."""
    sec = db.execute(
        select(Security).where(Security.cusip == cusip.upper())
    ).scalar_one_or_none()
    if sec is None:
        raise HTTPException(404, "security not found")

    # Latest holding per filer for this security.
    rows = db.execute(
        select(Holding, Filing, Filer)
        .join(Filing, Holding.filing_id == Filing.id)
        .join(Filer, Filing.filer_id == Filer.id)
        .where(Holding.security_id == sec.id)
        .order_by(Filer.id, Filing.period_of_report.desc().nullslast())
    ).all()

    seen: set[int] = set()
    out: list[HolderOut] = []
    for holding, filing, filer in rows:
        if filer.id in seen:
            continue
        seen.add(filer.id)
        out.append(
            HolderOut(
                filer=FilerOut.model_validate(filer),
                shares=holding.shares,
                value=holding.value,
                period_of_report=filing.period_of_report,
            )
        )
    out.sort(key=lambda h: h.value, reverse=True)
    return out
