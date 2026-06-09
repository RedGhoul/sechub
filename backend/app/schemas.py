"""Pydantic response models for the API."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class SecurityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cusip: str | None
    name: str
    ticker: str | None


class FilerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cik: str
    name: str
    kind: str
    latest_filing_at: date | None


class HoldingOut(BaseModel):
    security: SecurityOut
    value: int
    shares: int
    sh_prn_type: str
    put_call: str | None
    investment_discretion: str | None = None
    voting_sole: int = 0
    voting_shared: int = 0
    voting_none: int = 0
    pct_of_portfolio: float | None = None


class FilerDetailOut(BaseModel):
    filer: FilerOut
    period_of_report: date | None
    total_value: int
    position_count: int
    holdings: list[HoldingOut]


class HoldingChangeOut(BaseModel):
    security: SecurityOut
    action: str
    shares_delta: int
    value_delta: int
    pct_change: float | None


class ChangesOut(BaseModel):
    filer: FilerOut
    period: date | None
    prev_period: date | None
    changes: list[HoldingChangeOut]


class FilingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    accession_no: str
    form_type: str
    filed_at: date
    period_of_report: date | None
    source_url: str
    filer: FilerOut


class HolderOut(BaseModel):
    filer: FilerOut
    shares: int
    value: int
    period_of_report: date | None


class PeriodOut(BaseModel):
    """One 13F reporting period in a filer's history (for the time selector)."""

    period: date
    total_value: int
    position_count: int


class FundHoldingOut(BaseModel):
    security: SecurityOut
    value: int
    balance: float | None
    pct_of_net_assets: float | None


class StakeOut(BaseModel):
    """A 13D/13G beneficial-ownership stake, with both sides of the relation."""

    filer: FilerOut  # who holds the stake
    security: SecurityOut  # the company they hold it in
    form_type: str
    percent_of_class: float | None
    shares: int | None
    event_date: date | None
    is_activist: bool


class InsiderTxnOut(BaseModel):
    security: SecurityOut  # the issuer the insider trades in
    insider_name: str
    insider_title: str | None
    is_director: bool
    is_officer: bool
    is_ten_pct_owner: bool
    txn_date: date | None
    txn_code: str | None
    is_derivative: bool
    security_title: str | None
    shares: float | None
    price: float | None
    acquired_disposed: str | None
    shares_owned_after: float | None


class IssuerActivityOut(BaseModel):
    """The 'company' side of an entity: activity in *its own* securities.

    Best-effort: securities are matched to the filer by name, since the SEC does
    not provide a clean filer-CIK ↔ issuer-security join.
    """

    securities: list[SecurityOut]
    insider_txns: list[InsiderTxnOut]
    stakes_in: list[StakeOut]
    top_holders: list[HolderOut]
