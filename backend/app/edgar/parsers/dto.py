"""Plain data-transfer objects returned by parsers.

These intentionally mirror — but are decoupled from — the ORM models, so
parsers carry no database concerns and stay easy to test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class SecurityRef:
    cusip: str
    name: str


@dataclass
class Holding13F:
    security: SecurityRef
    value: int  # USD (normalized)
    shares: int
    sh_prn_type: str = "SH"
    put_call: str | None = None
    investment_discretion: str | None = None
    voting_sole: int = 0
    voting_shared: int = 0
    voting_none: int = 0


@dataclass
class Filing13F:
    period_of_report: date | None
    holdings: list[Holding13F] = field(default_factory=list)


@dataclass
class InsiderTransaction:
    txn_date: date | None
    txn_code: str | None
    is_derivative: bool
    security_title: str | None
    shares: float | None
    price: float | None
    acquired_disposed: str | None
    shares_owned_after: float | None


@dataclass
class OwnershipFiling:
    issuer: SecurityRef
    insider_name: str
    insider_title: str | None
    is_director: bool
    is_officer: bool
    is_ten_pct_owner: bool
    period_of_report: date | None
    transactions: list[InsiderTransaction] = field(default_factory=list)


@dataclass
class StakeFiling:
    issuer: SecurityRef
    percent_of_class: float | None
    shares: int | None
    event_date: date | None
    is_activist: bool


@dataclass
class FundHoldingRow:
    security: SecurityRef
    value: int
    balance: float | None
    pct_of_net_assets: float | None


@dataclass
class NportFiling:
    period_of_report: date | None
    holdings: list[FundHoldingRow] = field(default_factory=list)
