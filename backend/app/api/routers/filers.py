"""Filer endpoints: search, portfolio profile (current & historical), changes,
fund holdings, stakes held, and the issuer-side ('company') view."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.edgar.common import format_cik
from app.models import (
    Filer,
    Filing,
    FundHolding,
    Holding,
    HoldingChange,
    InsiderTxn,
    OwnershipStake,
    Security,
)
from app.schemas import (
    ChangesOut,
    FilerDetailOut,
    FilerOut,
    FundHoldingOut,
    HoldingChangeOut,
    HoldingOut,
    HolderOut,
    InsiderTxnOut,
    IssuerActivityOut,
    PeriodOut,
    SecurityOut,
    StakeOut,
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


def _latest_13f_period(db: Session, filer_id: int) -> date | None:
    return db.execute(
        select(Filing.period_of_report)
        .where(Filing.filer_id == filer_id, Filing.form_type.like("13F%"))
        .order_by(Filing.period_of_report.desc().nullslast())
        .limit(1)
    ).scalar_one_or_none()


@router.get("/{cik}/periods", response_model=list[PeriodOut])
def filer_periods(cik: str, db: Session = Depends(get_session)) -> list[PeriodOut]:
    """Every 13F reporting period this filer has on record, newest first.

    Powers the historical quarter selector and a portfolio-value-over-time view.
    """
    filer = _resolve_filer(db, cik)
    rows = db.execute(
        select(
            Filing.period_of_report,
            func.coalesce(func.sum(Holding.value), 0),
            func.count(Holding.id),
        )
        .join(Holding, Holding.filing_id == Filing.id)
        .where(Filing.filer_id == filer.id, Filing.form_type.like("13F%"))
        .group_by(Filing.period_of_report)
        .order_by(Filing.period_of_report.desc().nullslast())
    ).all()
    return [
        PeriodOut(period=period, total_value=int(total), position_count=count)
        for period, total, count in rows
        if period is not None
    ]


@router.get("/{cik}", response_model=FilerDetailOut)
def filer_detail(
    cik: str,
    period: date | None = Query(None, description="YYYY-MM-DD; defaults to latest"),
    db: Session = Depends(get_session),
) -> FilerDetailOut:
    """The filer's 13F portfolio for a period (latest by default), with each
    position's % of the portfolio."""
    filer = _resolve_filer(db, cik)

    target_period = period or _latest_13f_period(db, filer.id)

    holdings: list[Holding] = []
    if target_period is not None:
        holdings = list(
            db.execute(
                select(Holding)
                .join(Filing, Holding.filing_id == Filing.id)
                .where(
                    Filing.filer_id == filer.id,
                    Filing.period_of_report == target_period,
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
        period_of_report=target_period,
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


@router.get("/{cik}/fund-holdings", response_model=list[FundHoldingOut])
def filer_fund_holdings(
    cik: str,
    period: date | None = Query(None, description="YYYY-MM-DD; defaults to latest N-PORT"),
    limit: int = Query(500, le=2000),
    db: Session = Depends(get_session),
) -> list[FundHoldingOut]:
    """A fund's NPORT-P portfolio for a period (latest by default)."""
    filer = _resolve_filer(db, cik)

    target_period = period
    if target_period is None:
        target_period = db.execute(
            select(Filing.period_of_report)
            .join(FundHolding, FundHolding.filing_id == Filing.id)
            .where(Filing.filer_id == filer.id)
            .order_by(Filing.period_of_report.desc().nullslast())
            .limit(1)
        ).scalar_one_or_none()

    if target_period is None:
        return []

    rows = list(
        db.execute(
            select(FundHolding)
            .join(Filing, FundHolding.filing_id == Filing.id)
            .where(Filing.filer_id == filer.id, Filing.period_of_report == target_period)
            .order_by(FundHolding.value.desc())
            .limit(limit)
        ).scalars()
    )
    return [
        FundHoldingOut(
            security=SecurityOut.model_validate(h.security),
            value=h.value,
            balance=float(h.balance) if h.balance is not None else None,
            pct_of_net_assets=float(h.pct_of_net_assets) if h.pct_of_net_assets is not None else None,
        )
        for h in rows
    ]


@router.get("/{cik}/stakes-held", response_model=list[StakeOut])
def filer_stakes_held(
    cik: str,
    limit: int = Query(200, le=500),
    db: Session = Depends(get_session),
) -> list[StakeOut]:
    """13D/13G beneficial-ownership stakes this filer holds in other companies."""
    filer = _resolve_filer(db, cik)
    rows = db.execute(
        select(OwnershipStake, Filing)
        .join(Filing, OwnershipStake.filing_id == Filing.id)
        .where(Filing.filer_id == filer.id)
        .order_by(Filing.filed_at.desc())
        .limit(limit)
    ).all()
    return [
        StakeOut(
            filer=FilerOut.model_validate(filer),
            security=SecurityOut.model_validate(stake.security),
            form_type=filing.form_type,
            percent_of_class=float(stake.percent_of_class) if stake.percent_of_class is not None else None,
            shares=stake.shares,
            event_date=stake.event_date,
            is_activist=stake.is_activist,
        )
        for stake, filing in rows
    ]


def _issuer_securities(db: Session, filer: Filer) -> list[Security]:
    """Securities that represent this filer's own company.

    A company shows up as a ``Security`` only through *other* filers' documents
    about it (Form 4 insider trades, 13D/G stakes). Form 3/4/5 record the
    issuer's CIK, so we join on that exactly; for sources that don't (e.g.
    13D/G cover pages), we fall back to a best-effort name match.
    """
    return list(
        db.execute(
            select(Security).where(
                or_(Security.issuer_cik == filer.cik, Security.name.ilike(filer.name))
            )
        ).scalars()
    )


@router.get("/{cik}/issuer-activity", response_model=IssuerActivityOut)
def filer_issuer_activity(
    cik: str,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_session),
) -> IssuerActivityOut:
    """The 'company' side: insider trades, activist stakes, and institutional
    holders of this entity's *own* securities."""
    filer = _resolve_filer(db, cik)
    securities = _issuer_securities(db, filer)
    if not securities:
        return IssuerActivityOut(securities=[], insider_txns=[], stakes_in=[], top_holders=[])

    sec_ids = [s.id for s in securities]

    insider_rows = list(
        db.execute(
            select(InsiderTxn)
            .where(InsiderTxn.security_id.in_(sec_ids))
            .order_by(InsiderTxn.txn_date.desc().nullslast())
            .limit(limit)
        ).scalars()
    )
    insider_txns = [
        InsiderTxnOut(
            security=SecurityOut.model_validate(t.security),
            insider_name=t.insider_name,
            insider_title=t.insider_title,
            is_director=t.is_director,
            is_officer=t.is_officer,
            is_ten_pct_owner=t.is_ten_pct_owner,
            txn_date=t.txn_date,
            txn_code=t.txn_code,
            is_derivative=t.is_derivative,
            shares=float(t.shares) if t.shares is not None else None,
            price=float(t.price) if t.price is not None else None,
            acquired_disposed=t.acquired_disposed,
        )
        for t in insider_rows
    ]

    stake_rows = db.execute(
        select(OwnershipStake, Filing, Filer)
        .join(Filing, OwnershipStake.filing_id == Filing.id)
        .join(Filer, Filing.filer_id == Filer.id)
        .where(OwnershipStake.security_id.in_(sec_ids))
        .order_by(Filing.filed_at.desc())
        .limit(limit)
    ).all()
    stakes_in = [
        StakeOut(
            filer=FilerOut.model_validate(holder),
            security=SecurityOut.model_validate(stake.security),
            form_type=filing.form_type,
            percent_of_class=float(stake.percent_of_class) if stake.percent_of_class is not None else None,
            shares=stake.shares,
            event_date=stake.event_date,
            is_activist=stake.is_activist,
        )
        for stake, filing, holder in stake_rows
    ]

    # Top institutional holders: latest 13F position per filer for these securities.
    holder_rows = db.execute(
        select(Holding, Filing, Filer)
        .join(Filing, Holding.filing_id == Filing.id)
        .join(Filer, Filing.filer_id == Filer.id)
        .where(Holding.security_id.in_(sec_ids))
        .order_by(Filer.id, Filing.period_of_report.desc().nullslast())
    ).all()
    seen: set[int] = set()
    top_holders: list[HolderOut] = []
    for holding, filing, holder in holder_rows:
        if holder.id in seen:
            continue
        seen.add(holder.id)
        top_holders.append(
            HolderOut(
                filer=FilerOut.model_validate(holder),
                shares=holding.shares,
                value=holding.value,
                period_of_report=filing.period_of_report,
            )
        )
    top_holders.sort(key=lambda h: h.value, reverse=True)
    top_holders = top_holders[:limit]

    return IssuerActivityOut(
        securities=[SecurityOut.model_validate(s) for s in securities],
        insider_txns=insider_txns,
        stakes_in=stakes_in,
        top_holders=top_holders,
    )
