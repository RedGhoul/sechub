"""13F holdings and the derived quarter-over-quarter change records."""

from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Holding(Base):
    """A single row of a 13F information table (one issuer position).

    ``value`` is stored in **dollars**, normalized on ingest (pre-2023 filings
    report thousands; we multiply those up). ``shares`` is the share/principal
    amount; ``sh_prn_type`` distinguishes SH (shares) from PRN (principal).
    """

    __tablename__ = "holding"

    id: Mapped[int] = mapped_column(primary_key=True)
    filing_id: Mapped[int] = mapped_column(ForeignKey("filing.id", ondelete="CASCADE"), index=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("security.id"), index=True)

    value: Mapped[int] = mapped_column(BigInteger, default=0)  # USD
    shares: Mapped[int] = mapped_column(BigInteger, default=0)
    sh_prn_type: Mapped[str] = mapped_column(String(4), default="SH")

    # Options: "Put", "Call", or NULL for the underlying.
    put_call: Mapped[str | None] = mapped_column(String(4), nullable=True)
    investment_discretion: Mapped[str | None] = mapped_column(String(16), nullable=True)

    voting_sole: Mapped[int] = mapped_column(BigInteger, default=0)
    voting_shared: Mapped[int] = mapped_column(BigInteger, default=0)
    voting_none: Mapped[int] = mapped_column(BigInteger, default=0)

    security = relationship("Security")
    filing = relationship("Filing")

    __table_args__ = (Index("ix_holding_filing_security", "filing_id", "security_id"),)


class HoldingChange(Base):
    """Quarter-over-quarter delta for a filer's position in one security.

    Computed by ``ingest/diff.py`` when a new 13F lands, comparing against the
    filer's prior period. Powers the "what did they buy/sell" view.
    """

    __tablename__ = "holding_change"

    id: Mapped[int] = mapped_column(primary_key=True)
    filer_id: Mapped[int] = mapped_column(ForeignKey("filer.id"), index=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("security.id"), index=True)

    period: Mapped[date] = mapped_column(Date, index=True)
    prev_period: Mapped[date | None] = mapped_column(Date, nullable=True)

    # NEW | ADD | TRIM | EXIT | HOLD
    action: Mapped[str] = mapped_column(String(8), index=True)
    shares_delta: Mapped[int] = mapped_column(BigInteger, default=0)
    value_delta: Mapped[int] = mapped_column(BigInteger, default=0)
    pct_change: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)

    security = relationship("Security")

    __table_args__ = (
        Index("ix_change_filer_period", "filer_id", "period"),
    )
