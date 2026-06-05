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
