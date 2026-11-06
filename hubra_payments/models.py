"""The club's Stripe account and its checkouts (one copy per club schema)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PaymentAccount(db.Model):
    """The club's connected Stripe account (at most one row)."""

    __tablename__ = "payments_account"

    id: Mapped[int] = mapped_column(primary_key=True)
    stripe_account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    livemode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Mirrors of the Stripe account, refreshed on return and on "Prüfen".
    details_submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    charges_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    card: Mapped[bool] = mapped_column(Boolean, default=False)
    twint: Mapped[bool] = mapped_column(Boolean, default=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # The club passes the fees on: members pay the invoice plus a surcharge
    # sized so the club still gets the full invoice amount after Stripe's
    # fee (the club's rate, percent plus fixed) and the Hubra fee.
    pass_fees: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    surcharge_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0"), nullable=False
    )
    surcharge_fixed: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), default=Decimal("0"), nullable=False
    )
    connected_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PaymentCheckout(db.Model):
    """One Stripe Checkout Session for one invoice."""

    __tablename__ = "payments_checkouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    member_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    stripe_account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    # Part of amount the member paid on top of the invoice (0: none).
    surcharge: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="chf")
    # open → paid | expired
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
