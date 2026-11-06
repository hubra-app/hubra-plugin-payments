"""Payments API: /api/v1/app/payments.

GET    /status                      for everyone: may members pay online here?
POST   /connect                     admin: the Stripe page to set up the account
POST   /refresh                     admin: read the account's state from Stripe
DELETE /connect                     admin: forget the account
GET    /checkouts                   admin: the club's online payments
POST   /invoices/<id>/checkout      member: pay one's own open invoice
POST   /checkouts/confirm           member back from Stripe: {sessionId}
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from hubra.core.auth.helpers import get_current_member
from hubra.core.errors import api_error
from hubra.core.extensions import db
from hubra.core.models.finance import Invoice
from hubra.core.models.member import Member
from hubra.core.permissions import (
    member_has_permission,
    permission_required,
    require_member,
)

from . import services
from .models import PaymentCheckout
from .stripe_api import StripeError

payments_bp = Blueprint("payments_bp", __name__)

MANAGE = "payments.account.manage"


def _stripe_failed(exc: StripeError):
    return api_error("STRIPE_ERROR", str(exc), 502)


def _payment_failed(exc: services.PaymentError):
    return api_error(exc.code, exc.message, exc.status)


def _account_dict() -> dict | None:
    acc = services.account()
    if acc is None:
        return None
    return {
        "id": acc.stripe_account_id,
        "name": acc.display_name,
        "livemode": acc.livemode,
        "detailsSubmitted": bool(acc.details_submitted),
        "chargesEnabled": bool(acc.charges_enabled),
        "card": bool(acc.card),
        "twint": bool(acc.twint),
        "checkedAt": acc.checked_at.isoformat() if acc.checked_at else None,
    }


def _checkout_dict(chk: PaymentCheckout, names: dict[int, str]) -> dict:
    return {
        "id": chk.id,
        "invoiceId": chk.invoice_id,
        "memberId": chk.member_id,
        "memberName": names.get(chk.member_id or 0),
        "amount": float(chk.amount),
        "fee": float(chk.fee or 0),
        "status": chk.status,
        "method": chk.method,
        "createdAt": chk.created_at.isoformat() if chk.created_at else None,
        "paidAt": chk.paid_at.isoformat() if chk.paid_at else None,
    }


@payments_bp.get("/status")
@require_member
def status():
    member = get_current_member()
    manager = member_has_permission(member, MANAGE)
    platform = services.platform()
    out = {
        "platform": platform is not None,
        "testMode": bool(platform and platform.test_mode),
        "ready": services.ready(),
        "memberId": member.id if member else None,
        "canManage": manager,
    }
    if manager:
        out["account"] = _account_dict()
        out["feePercent"] = platform.fee_percent if platform else 0
    return jsonify(out), 200


@payments_bp.post("/connect")
@permission_required("account", "manage", "Connect Stripe and see online payments")
def connect():
    from hubra.core.tenant.context import current_tenant

    tenant = current_tenant()
    try:
        url = services.connect(get_current_member(), tenant.name if tenant else None)
    except services.PaymentError as exc:
        return _payment_failed(exc)
    except StripeError as exc:
        db.session.rollback()
        return _stripe_failed(exc)
    db.session.commit()
    return jsonify({"url": url}), 200


@payments_bp.post("/refresh")
@permission_required("account", "manage", "Connect Stripe and see online payments")
def refresh():
    try:
        services.refresh()
    except services.PaymentError as exc:
        return _payment_failed(exc)
    except StripeError as exc:
        return _stripe_failed(exc)
    db.session.commit()
    return jsonify({"account": _account_dict(), "ready": services.ready()}), 200


@payments_bp.delete("/connect")
@permission_required("account", "manage", "Connect Stripe and see online payments")
def disconnect():
    services.disconnect(get_current_member())
    db.session.commit()
    return "", 204


@payments_bp.get("/checkouts")
@permission_required("account", "manage", "Connect Stripe and see online payments")
def checkouts():
    rows = db.session.scalars(
        select(PaymentCheckout).order_by(PaymentCheckout.id.desc()).limit(200)
    ).all()
    ids = {c.member_id for c in rows if c.member_id}
    names = {
        m.id: f"{m.first_name} {m.last_name}".strip()
        for m in (
            db.session.scalars(select(Member).where(Member.id.in_(ids))) if ids else []
        )
    }
    return jsonify([_checkout_dict(c, names) for c in rows]), 200


@payments_bp.post("/invoices/<int:invoice_id>/checkout")
@require_member
def checkout(invoice_id: int):
    member = get_current_member()
    invoice = db.session.get(Invoice, invoice_id)
    # Only the member the invoice is for pays it here.
    if invoice is None or member is None or invoice.member_id != member.id:
        return api_error("NOT_FOUND", "Invoice not found", 404)
    try:
        chk = services.start_checkout(invoice, member)
    except services.PaymentError as exc:
        return _payment_failed(exc)
    except StripeError as exc:
        db.session.rollback()
        return _stripe_failed(exc)
    db.session.commit()
    return jsonify({"url": chk.url, "checkoutId": chk.id}), 200


@payments_bp.post("/checkouts/confirm")
@require_member
def confirm():
    member = get_current_member()
    session_id = str((request.get_json(silent=True) or {}).get("sessionId") or "")
    chk = db.session.scalar(
        select(PaymentCheckout).where(PaymentCheckout.session_id == session_id)
    )
    if chk is None or member is None or chk.member_id != member.id:
        return api_error("NOT_FOUND", "Payment not found", 404)
    try:
        state = services.sync(chk)
    except StripeError as exc:
        db.session.commit()
        return _stripe_failed(exc)
    db.session.commit()
    return jsonify(
        {"status": state, "invoiceId": chk.invoice_id, "amount": float(chk.amount)}
    ), 200
