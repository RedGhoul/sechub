"""Quarter-over-quarter 13F diff: classify each position as NEW/ADD/TRIM/EXIT/HOLD.

When a new 13F is ingested we compare the filer's positions for the new period
against their most recent *prior* period and write ``HoldingChange`` rows. These
power the "what did they buy/sell this quarter" view.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Filing, Holding, HoldingChange


def _positions_for_period(db: Session, filer_id: int, period: date) -> dict[int, tuple[int, int]]:
    """Map security_id -> (shares, value) summed across the filer's filing(s)
    for ``period`` (an amended 13F can split positions across filings)."""
    rows = db.execute(
        select(Holding.security_id, Holding.shares, Holding.value)
        .join(Filing, Holding.filing_id == Filing.id)
        .where(Filing.filer_id == filer_id, Filing.period_of_report == period)
    ).all()
    agg: dict[int, tuple[int, int]] = {}
    for sec_id, shares, value in rows:
        cur = agg.get(sec_id, (0, 0))
        agg[sec_id] = (cur[0] + (shares or 0), cur[1] + (value or 0))
    return agg


def _prior_period(db: Session, filer_id: int, period: date) -> date | None:
    return db.execute(
        select(Filing.period_of_report)
        .where(
            Filing.filer_id == filer_id,
            Filing.form_type.like("13F%"),
            Filing.period_of_report < period,
            Filing.period_of_report.is_not(None),
        )
        .order_by(Filing.period_of_report.desc())
        .limit(1)
    ).scalar_one_or_none()


def compute_changes(db: Session, filer_id: int, period: date) -> int:
    """(Re)compute HoldingChange rows for one filer+period. Returns row count."""
    prior = _prior_period(db, filer_id, period)
    current = _positions_for_period(db, filer_id, period)
    previous = _positions_for_period(db, filer_id, prior) if prior else {}

    # Clear any prior computation for idempotency.
    db.query(HoldingChange).filter(
        HoldingChange.filer_id == filer_id, HoldingChange.period == period
    ).delete()

    changes: list[HoldingChange] = []
    for sec_id in set(current) | set(previous):
        cur_shares, cur_value = current.get(sec_id, (0, 0))
        prev_shares, prev_value = previous.get(sec_id, (0, 0))
        action = _classify(prev_shares, cur_shares)
        if action == "HOLD" and cur_shares == prev_shares:
            continue  # nothing changed; skip noise
        pct = None
        if prev_shares:
            pct = round((cur_shares - prev_shares) / prev_shares * 100, 4)
        changes.append(
            HoldingChange(
                filer_id=filer_id,
                security_id=sec_id,
                period=period,
                prev_period=prior,
                action=action,
                shares_delta=cur_shares - prev_shares,
                value_delta=cur_value - prev_value,
                pct_change=pct,
            )
        )
    db.add_all(changes)
    db.flush()
    return len(changes)


def _classify(prev_shares: int, cur_shares: int) -> str:
    if prev_shares == 0 and cur_shares > 0:
        return "NEW"
    if cur_shares == 0 and prev_shares > 0:
        return "EXIT"
    if cur_shares > prev_shares:
        return "ADD"
    if cur_shares < prev_shares:
        return "TRIM"
    return "HOLD"
