"""Resumable cursor for the historical full-index backfill."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BackfillProgress(Base):
    """One row per ``(year, quarter)`` segment of the full-index backfill.

    The backfill processes a whole quarter's index at a time. A row with
    ``completed_at`` set means that segment is done, so a re-run skips it — the
    job is interruptible and resumable. (Ingestion itself is idempotent on
    accession number, so re-processing a segment would be harmless anyway; the
    cursor just avoids redoing the work.)
    """

    __tablename__ = "backfill_progress"

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer)
    quarter: Mapped[int] = mapped_column(Integer)
    forms: Mapped[str] = mapped_column(String(255), default="")

    filings_seen: Mapped[int] = mapped_column(Integer, default=0)
    filings_ingested: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("year", "quarter", name="uq_backfill_year_quarter"),)
