"""Connecting the club's Stripe account, and paying invoices through it."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select

from hubra.core.extensions import db
from hubra.core.models.finance import Invoice
from hubra.core.services import platform_settings
from hubra.core.utils import log_audit

from . import stripe_api
from .models import PaymentAccount, PaymentCheckout
from .stripe_api import StripeError

_log = logging.getLogger(__name__)

CURRENCY = "chf"
# An open checkout is used again while it has this long left; after that a
# member who clicks "Pay" gets a fresh one.
REUSE_MARGIN = timedelta(minutes=10)
# Stripe ends a Checkout Session after 24 hours; past this we stop asking.
GIVE_UP = timedelta(hours=26)


class PaymentError(Exception):
    """Something the member or the admin should read (error code + message)."""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def platform() -> platform_settings.StripePlatform | None:
    return platform_settings.stripe()


def _key() -> str:
    p = platform()
    if p is None:
        raise PaymentError(
            "PAYMENTS_NOT_SET_UP",
            "Online payments are not set up on this platform yet.",
            409,
        )
    return p.secret_key


def account() -> PaymentAccount | None:
    return db.session.scalar(select(PaymentAccount).order_by(PaymentAccount.id))


def ready() -> bool:
    acc = account()
    return bool(platform() and acc and acc.charges_enabled)


def cents(amount: Decimal | float | int | str) -> int:
    return int(
        (Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


# ── Club URLs ────────────────────────────────────────────────────────────────


def club_url(path: str) -> str:
    """An address in this club's app (Stripe sends the browser back there)."""
    from hubra.core.services.email import _get_base_url
    from hubra.core.tenant.context import current_tenant

    base = _get_base_url()
    tenant = current_tenant()
    if tenant is not None:
        base = f"{base}/{tenant.slug}"
    return f"{base}{path}"


# ── Account ──────────────────────────────────────────────────────────────────


def _apply_account(acc: PaymentAccount, data: dict) -> None:
    caps = data.get("capabilities") or {}
    acc.details_submitted = bool(data.get("details_submitted"))
    acc.charges_enabled = bool(data.get("charges_enabled"))
    acc.card = caps.get("card_payments") == "active"
    acc.twint = caps.get("twint_payments") == "active"
    dashboard = (data.get("settings") or {}).get("dashboard") or {}
    profile = data.get("business_profile") or {}
    acc.display_name = (dashboard.get("display_name") or profile.get("name") or "")[
        :200
    ] or None
    acc.checked_at = _now()


def connect(member, club_name: str | None) -> str:
    """The Stripe page where the club sets up (or finishes) its account."""
    key = _key()
    acc = account()
    if acc is None:
        data = stripe_api.create_account(key, getattr(member, "email", None), club_name)
        acc = PaymentAccount(
            stripe_account_id=data["id"],
            livemode=bool(data.get("livemode")),
            connected_by=member.id if member else None,
        )
        _apply_account(acc, data)
        db.session.add(acc)
        db.session.flush()
        log_audit(
            member.id if member else None,
            "payments.connected",
            "payments_account",
            acc.id,
            data["id"],
        )
    return stripe_api.account_link(
        key,
        acc.stripe_account_id,
        refresh_url=club_url("/app/payments?refresh=1"),
        return_url=club_url("/app/payments?connected=1"),
    )


def refresh() -> PaymentAccount | None:
    acc = account()
    if acc is None:
        return None
    _apply_account(acc, stripe_api.get_account(_key(), acc.stripe_account_id))
    return acc


def disconnect(member) -> None:
    """Forget the account. Open checkouts are ended; the Stripe account and
    its money stay the club's."""
    acc = account()
    if acc is None:
        return
    p = platform()
    for chk in db.session.scalars(
        select(PaymentCheckout).where(PaymentCheckout.status == "open")
    ):
        if p is not None:
            try:
                stripe_api.expire_checkout(
                    p.secret_key, chk.stripe_account_id, chk.session_id
                )
            except StripeError as exc:
                _log.info("payments: could not end checkout %s: %s", chk.id, exc)
        chk.status = "expired"
    log_audit(
        member.id if member else None,
        "payments.disconnected",
        "payments_account",
        acc.id,
        acc.stripe_account_id,
    )
    db.session.delete(acc)


# ── Checkout ─────────────────────────────────────────────────────────────────


def _reusable(invoice: Invoice, amount: int) -> PaymentCheckout | None:
    chk = db.session.scalar(
        select(PaymentCheckout)
        .where(PaymentCheckout.invoice_id == invoice.id)
        .where(PaymentCheckout.status == "open")
        .order_by(PaymentCheckout.id.desc())
    )
    if chk is None or cents(chk.amount) != amount or not chk.url:
        return None
    expires = _aware(chk.expires_at)
    if expires is None or expires - _now() < REUSE_MARGIN:
        return None
    return chk


def start_checkout(invoice: Invoice, member) -> PaymentCheckout:
    p = platform()
    acc = account()
    if p is None or acc is None or not acc.charges_enabled:
        raise PaymentError(
            "PAYMENTS_NOT_READY", "This club doesn't take online payments yet.", 409
        )
    if invoice.status == "Paid":
        raise PaymentError("INVOICE_PAID", "This invoice is already paid.", 409)
    amount = cents(invoice.amount)
    if amount < 50:
        raise PaymentError(
            "AMOUNT_TOO_SMALL", "Online payments start at CHF 0.50.", 400
        )
    reuse = _reusable(invoice, amount)
    if reuse is not None:
        return reuse

    fee = int(
        (Decimal(amount) * Decimal(str(p.fee_percent)) / 100).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    tries = db.session.scalar(
        select(func.count(PaymentCheckout.id)).where(
            PaymentCheckout.invoice_id == invoice.id
        )
    )
    from hubra.core.tenant.context import current_tenant

    tenant = current_tenant()
    label = f"Rechnung {invoice.id}"
    if invoice.description:
        label = f"{label}: {invoice.description}"[:250]
    meta = {
        "hubra_invoice": invoice.id,
        "hubra_member": member.id,
        "hubra_club": tenant.slug if tenant else "",
    }
    data = {
        "mode": "payment",
        "line_items": [
            {
                "quantity": 1,
                "price_data": {
                    "currency": CURRENCY,
                    "unit_amount": amount,
                    "product_data": {"name": label},
                },
            }
        ],
        # No payment_method_types: Stripe offers what the club turned on in
        # its dashboard (card, TWINT, ...) for CHF.
        "success_url": club_url(
            "/app/payments/return?session_id={CHECKOUT_SESSION_ID}"
        ),
        "cancel_url": club_url(f"/app/payments/return?cancelled={invoice.id}"),
        "client_reference_id": str(invoice.id),
        "customer_email": getattr(member, "email", None) or None,
        "metadata": meta,
        "payment_intent_data": {
            "description": label,
            "metadata": meta,
            "application_fee_amount": fee or None,
        },
    }
    idem = f"hubra-{meta['hubra_club']}-inv{invoice.id}-{amount}-{tries}"
    session = stripe_api.create_checkout(
        p.secret_key, acc.stripe_account_id, data, idempotency_key=idem
    )
    expires = session.get("expires_at")
    chk = PaymentCheckout(
        invoice_id=invoice.id,
        member_id=member.id,
        stripe_account_id=acc.stripe_account_id,
        session_id=session["id"],
        url=session.get("url"),
        amount=Decimal(amount) / 100,
        fee=Decimal(fee) / 100,
        currency=CURRENCY,
        status="open",
        expires_at=(
            datetime.fromtimestamp(int(expires), timezone.utc)
            if expires
            else _now() + timedelta(hours=24)
        ),
    )
    db.session.add(chk)
    db.session.flush()
    return chk


def _method(session: dict) -> str | None:
    pi = session.get("payment_intent")
    if isinstance(pi, dict):
        pm = pi.get("payment_method")
        if isinstance(pm, dict) and pm.get("type"):
            return str(pm["type"])[:32]
        types = pi.get("payment_method_types") or []
        if len(types) == 1:
            return str(types[0])[:32]
    return None


def apply_session(chk: PaymentCheckout, session: dict) -> str:
    """Bring a checkout (and its invoice) up to what Stripe says."""
    if chk.status != "open":
        return chk.status
    if session.get("payment_status") == "paid":
        total = session.get("amount_total")
        currency = (session.get("currency") or "").lower()
        if total != cents(chk.amount) or currency != chk.currency:
            _log.warning(
                "payments: checkout %s paid %s %s, expected %s %s; not booked",
                chk.id,
                total,
                currency,
                cents(chk.amount),
                chk.currency,
            )
            return chk.status
        chk.status = "paid"
        chk.paid_at = _now()
        chk.method = _method(session)
        invoice = db.session.get(Invoice, chk.invoice_id) if chk.invoice_id else None
        if invoice is not None and invoice.status != "Paid":
            from hubra.core.contracts import SYSTEM, call

            # Stripe says it's paid; the member paying holds no invoice right.
            call(
                "finance.invoice.set_status",
                invoice_id=invoice.id,
                status="Paid",
                actor_id=chk.member_id,
                actor=SYSTEM,
            )
        log_audit(
            chk.member_id,
            "payments.paid",
            "invoice",
            chk.invoice_id,
            f"Rechnung {chk.invoice_id}: CHF {chk.amount} online"
            + (f" ({chk.method})" if chk.method else ""),
        )
    elif session.get("status") == "expired":
        chk.status = "expired"
    return chk.status


def sync(chk: PaymentCheckout) -> str:
    p = platform()
    if p is None or chk.status != "open":
        return chk.status
    try:
        session = stripe_api.get_checkout(
            p.secret_key, chk.stripe_account_id, chk.session_id
        )
    except StripeError as exc:
        if exc.status == 404 and _now() - _aware(chk.created_at) > GIVE_UP:
            chk.status = "expired"
        raise
    return apply_session(chk, session)


def sync_open() -> dict:
    """Ask Stripe about every open checkout (the scheduler, every 10 min)."""
    if platform() is None:
        return {"checked": 0}
    done = {"checked": 0, "paid": 0, "expired": 0, "failed": 0}
    open_ids = list(
        db.session.scalars(
            select(PaymentCheckout.id).where(PaymentCheckout.status == "open")
        )
    )
    for chk_id in open_ids:
        chk = db.session.get(PaymentCheckout, chk_id)
        done["checked"] += 1
        try:
            status = sync(chk)
        except StripeError as exc:
            _log.info("payments: checkout %s not checked: %s", chk_id, exc)
            done["failed"] += 1
            db.session.commit()
            continue
        if status == "open" and _now() - _aware(chk.created_at) > GIVE_UP:
            status = chk.status = "expired"
        if status in ("paid", "expired"):
            done[status] += 1
        db.session.commit()
    return done
