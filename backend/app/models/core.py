"""Core entities shared across all filing types: Filer, Security, Filing."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Filer(Base):
    """An entity that files with the SEC, keyed by CIK.

    Covers institutions (13F), insiders (Form 3/4/5), and funds (N-PORT). The
    ``kind`` column tags which role we first saw them in; a single CIK can wear
    more than one hat over time.
    """

    __tablename__ = "filer"

    id: Mapped[int] = mapped_column(primary_key=True)
    # CIK as a zero-padded 10-char string, e.g. "0001067983".
    cik: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    kind: Mapped[str] = mapped_column(String(32), default="institution")
    latest_filing_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    filings: Mapped[list["Filing"]] = relationship(back_populates="filer")


class Security(Base):
    """A security, deduplicated on a canonical ``key``.

    Different filings identify the same security differently: 13F/N-PORT use
    CUSIP, while Form 3/4/5 give a ticker + issuer CIK (no CUSIP). ``key`` is the
    best identifier available — ``"<cusip>"``, else ``"TICKER:<sym>"``, else
    ``"CIK:<cik>"`` — so every form resolves to one row (see
    ``ingest.resolve.get_or_create_security``).

    ``ticker`` is best-effort: the SEC publishes ticker↔CIK but not
    CUSIP↔ticker. A future live-price feature would join on it.
    """

    __tablename__ = "security"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    cusip: Mapped[str | None] = mapped_column(String(9), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    ticker: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    # The issuer's own CIK, when a filing names it (Form 3/4/5). Lets us join a
    # security back to the company's filer entity exactly, instead of by name.
    issuer_cik: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)


class Filing(Base):
    """One submission to EDGAR, uniquely identified by its accession number.

    ``accession_no`` is the idempotency key for the whole ingest pipeline: we
    never parse the same accession twice.
    """

    __tablename__ = "filing"

    id: Mapped[int] = mapped_column(primary_key=True)
    accession_no: Mapped[str] = mapped_column(String(25), unique=True, index=True)
    filer_id: Mapped[int] = mapped_column(ForeignKey("filer.id"), index=True)

    form_type: Mapped[str] = mapped_column(String(20), index=True)
    filed_at: Mapped[date] = mapped_column(Date, index=True)
    # Reporting period the filing describes (quarter-end for 13F, etc.).
    period_of_report: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    source_url: Mapped[str] = mapped_column(String(512))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    filer: Mapped[Filer] = relationship(back_populates="filings")

    __table_args__ = (UniqueConstraint("accession_no", name="uq_filing_accession"),)
