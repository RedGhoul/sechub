"""SC 13D / 13G beneficial-ownership stakes (best-effort, text-parsed)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class OwnershipStake(Base):
    """A >5% beneficial-ownership position from a Schedule 13D/13G.

    These schedules have **no standard structured table**, so fields are
    extracted best-effort from the cover page / primary document and may be
    incomplete. ``is_activist`` is True for 13D (active intent) vs 13G (passive).
    """

    __tablename__ = "ownership_stake"

    id: Mapped[int] = mapped_column(primary_key=True)
    filing_id: Mapped[int] = mapped_column(ForeignKey("filing.id", ondelete="CASCADE"), index=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("security.id"), index=True)

    percent_of_class: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    shares: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_activist: Mapped[bool] = mapped_column(default=False)

    security = relationship("Security")
    filing = relationship("Filing")
