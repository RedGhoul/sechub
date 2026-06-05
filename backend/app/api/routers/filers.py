"""Filer endpoints: search, portfolio profile, and quarter-over-quarter changes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.edgar.common import format_cik
from app.models import Filer, Filing, Holding, HoldingChange
from app.schemas import (
    ChangesOut,
    FilerDetailOut,
    FilerOut,
    HoldingChangeOut,
    HoldingOut,
    SecurityOut,
)

router = APIRouter(prefix="/filers", tags=["filers"])


@router.get("", response_model=list[FilerOut])
def list_filers(
    q: str | None = Query(None, description="name substring"),
    kind: str | None = Query(None, description="institution|insider|fund"),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_session),
) -> list[Filer]:
    stmt = select(Filer)
    if q:
        stmt = stmt.where(Filer.name.ilike(f"%{q}%"))
    if kind:
        stmt = stmt.where(Filer.kind == kind)
    stmt = stmt.order_by(Filer.latest_filing_at.desc().nullslast()).limit(limit)
    return list(db.execute(stmt).scalars())


def _resolve_filer(db: Session, cik: str) -> Filer:
    filer = db.execute(
        select(Filer).where(Filer.cik == format_cik(cik))
    ).scalar_one_or_none()
    if filer is None:
        raise HTTPException(404, "filer not found")
    return filer


@router.get("/{cik}", response_model=FilerDetailOut)
def filer_detail(cik: str, db: Session = Depends(get_session)) -> FilerDetailOut:
    """The filer's latest 13F portfolio with per-position % of portfolio."""
    filer = _resolve_filer(db, cik)

    latest_period = db.execute(
        select(Filing.period_of_report)
        .where(Filing.filer_id == filer.id, Filing.form_type.like("13F%"))
        .order_by(Filing.period_of_report.desc().nullslast())
        .limit(1)
    ).scalar_one_or_none()

    holdings: list[Holding] = []
    if latest_period is not None:
        holdings = list(
            db.execute(
                select(Holding)
                .join(Filing, Holding.filing_id == Filing.id)
                .where(
                    Filing.filer_id == filer.id,
                    Filing.period_of_report == latest_period,
                )
                .order_by(Holding.value.desc())
            ).scalars()
        )

    total_value = sum(h.value for h in holdings)
    out_holdings = [
        HoldingOut(
            security=SecurityOut.model_validate(h.security),
            value=h.value,
            shares=h.shares,
            sh_prn_type=h.sh_prn_type,
            put_call=h.put_call,
            pct_of_portfolio=round(h.value / total_value * 100, 2) if total_value else None,
        )
        for h in holdings
    ]

    return FilerDetailOut(
        filer=FilerOut.model_validate(filer),
        period_of_report=latest_period,
        total_value=total_value,
        position_count=len(holdings),
        holdings=out_holdings,
    )


@router.get("/{cik}/changes", response_model=ChangesOut)
def filer_changes(
    cik: str,
    period: str | None = Query(None, description="YYYY-MM-DD; defaults to latest"),
    db: Session = Depends(get_session),
) -> ChangesOut:
    """NEW / ADD / TRIM / EXIT positions for a quarter."""
    filer = _resolve_filer(db, cik)

    target_period = period
    if target_period is None:
        target_period = db.execute(
            select(HoldingChange.period)
            .where(HoldingChange.filer_id == filer.id)
            .order_by(HoldingChange.period.desc())
            .limit(1)
        ).scalar_one_or_none()

    rows: list[HoldingChange] = []
    prev_period = None
    if target_period is not None:
        rows = list(
            db.execute(
                select(HoldingChange)
                .where(
                    HoldingChange.filer_id == filer.id,
                    HoldingChange.period == target_period,
                )
                .order_by(func.abs(HoldingChange.value_delta).desc())
            ).scalars()
        )
        prev_period = rows[0].prev_period if rows else None

    return ChangesOut(
        filer=FilerOut.model_validate(filer),
        period=target_period,  # str from query or date from DB; pydantic coerces
        prev_period=prev_period,
        changes=[
            HoldingChangeOut(
                security=SecurityOut.model_validate(c.security),
                action=c.action,
                shares_delta=c.shares_delta,
                value_delta=c.value_delta,
                pct_change=float(c.pct_change) if c.pct_change is not None else None,
            )
            for c in rows
        ],
    )
