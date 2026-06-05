"""NPORT-P fund/ETF portfolio holdings."""

from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class FundHolding(Base):
    """One holding line from an NPORT-P monthly portfolio report."""

    __tablename__ = "fund_holding"

    id: Mapped[int] = mapped_column(primary_key=True)
    filing_id: Mapped[int] = mapped_column(ForeignKey("filing.id", ondelete="CASCADE"), index=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("security.id"), index=True)

    value: Mapped[int] = mapped_column(BigInteger, default=0)  # USD
    balance: Mapped[float | None] = mapped_column(Numeric(24, 4), nullable=True)
    pct_of_net_assets: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)

    security = relationship("Security")
    filing = relationship("Filing")
