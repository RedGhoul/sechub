"""Form 3/4/5 insider transactions."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class InsiderTxn(Base):
    """One transaction line from an ownership document (Form 3/4/5).

    Each filing can contain several non-derivative and derivative transactions;
    we store one row per line. ``acquired_disposed`` is "A" or "D".
    """

    __tablename__ = "insider_txn"

    id: Mapped[int] = mapped_column(primary_key=True)
    filing_id: Mapped[int] = mapped_column(ForeignKey("filing.id", ondelete="CASCADE"), index=True)
    # Issuer the insider trades in (the company), as a Security.
    security_id: Mapped[int] = mapped_column(ForeignKey("security.id"), index=True)

    insider_name: Mapped[str] = mapped_column(String(255), index=True)
    insider_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_director: Mapped[bool] = mapped_column(Boolean, default=False)
    is_officer: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ten_pct_owner: Mapped[bool] = mapped_column(Boolean, default=False)

    txn_date: Mapped[date | None] = mapped_column(Date, index=True)
    txn_code: Mapped[str | None] = mapped_column(String(4), nullable=True)
    is_derivative: Mapped[bool] = mapped_column(Boolean, default=False)
    security_title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    shares: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True)
    acquired_disposed: Mapped[str | None] = mapped_column(String(1), nullable=True)
    shares_owned_after: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True)

    security = relationship("Security")
    filing = relationship("Filing")
