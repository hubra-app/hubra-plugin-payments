"""Online payments: connecting Stripe, paying an invoice, the invoice turning
paid. Stripe is replaced by a small fake (no network).

Runs with Hubra's fixtures once the plugin is in plugins/payments of a
Hubra checkout (see README.md).
"""

from __future__ import annotations

import json
import time
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tests.helpers import set_modules
from tests.settings.test_settings_kv import _login, _make_role_and_member

BASE = "/api/v1/app/payments"
MANAGE = ["payments.account.manage"]


class FakeStripe:
    """Answers the calls the plugin makes, and remembers them."""

    def __init__(self):
        self.calls: list[dict] = []
        self.account = {
            "id": "acct_club",
            "livemode": False,
            "details_submitted": False,
            "charges_enabled": False,
            "capabilities": {},
            "business_profile": {"name": "FC Test"},
        }
        self.sessions: dict[str, dict] = {}

    def finish_onboarding(self):
        self.account.update(
            details_submitted=True,
            charges_enabled=True,
            capabilities={"card_payments": "active", "twint_payments": "active"},
        )

    def pay(self, sid: str, method="twint", amount=None):
        s = self.sessions[sid]
        s.update(status="complete", payment_status="paid")
        if amount is not None:
            s["amount_total"] = amount
        s["payment_intent"] = {"payment_method": {"type": method}}

    def __call__(self, method, url, headers, body):
        parsed = urllib.parse.urlparse(url)
        form = dict(urllib.parse.parse_qsl(body.decode())) if body else {}
        self.calls.append(
            {"method": method, "path": parsed.path, "headers": headers, "form": form}
        )
        path = parsed.path
        if path == "/v1/accounts" and method == "POST":
            return 200, json.dumps(self.account).encode()
        if path == "/v1/accounts/acct_club":
            return 200, json.dumps(self.account).encode()
        if path == "/v1/account_links":
            return 200, json.dumps(
                {"url": "https://connect.stripe.com/setup/s/x"}
            ).encode()
        if path == "/v1/checkout/sessions" and method == "POST":
            sid = f"cs_test_{len(self.sessions) + 1}"
            self.sessions[sid] = {
                "id": sid,
                "url": f"https://checkout.stripe.com/c/pay/{sid}",
                "status": "open",
                "payment_status": "unpaid",
                "amount_total": int(form["line_items[0][price_data][unit_amount]"]),
                "currency": form["line_items[0][price_data][currency]"],
                "expires_at": int(time.time()) + 86400,
            }
            return 200, json.dumps(self.sessions[sid]).encode()
        if path.startswith("/v1/checkout/sessions/"):
            sid = path.split("/")[4]
            if sid not in self.sessions:
                return 404, b'{"error": {"message": "No such session"}}'
            if path.endswith("/expire"):
                self.sessions[sid]["status"] = "expired"
            return 200, json.dumps(self.sessions[sid]).encode()
        return 404, b'{"error": {"message": "unknown"}}'


@pytest.fixture
def stripe(monkeypatch):
    from hubra_payments import stripe_api

    fake = FakeStripe()
    monkeypatch.setattr(stripe_api, "_send", fake)
    return fake


@pytest.fixture
def club(client, app, db, seeded_db, stripe):
    """Payments on with a platform key; Tina (manage) and Mia (no rights)
    with an open invoice of CHF 120."""
    from hubra.core.models.finance import Invoice
    from hubra.core.services import platform_settings

    set_modules(True, "finance", "payments")
    app.test_cli_runner().invoke(args=["sync-permissions"])
    platform_settings.set_many(
        {
            "payments.stripe.secret_key": "sk_test_abcdefghijklmnop",
            "payments.fee_percent": "1.5",
        }
    )
    tier = seeded_db["tier"]
    _make_role_and_member(db, tier, name="Tina", permission_keys=MANAGE)
    mia = _make_role_and_member(db, tier, name="Mia", permission_keys=[])
    other = _make_role_and_member(db, tier, name="Otto", permission_keys=[])
    today = date.today()
    inv = Invoice(
        member_id=mia.id,
        issued=today,
        due=today + timedelta(days=30),
        amount=Decimal("120.00"),
        status="Open",
        purpose="other",
        description="Jahresbeitrag",
    )
    db.session.add(inv)
    db.session.commit()
    return {"invoice": inv.id, "mia": mia.id, "other": other.id}


def _connect(client, stripe):
    _login(client, "tina@test.ch")
    r = client.post(f"{BASE}/connect")
    assert r.status_code == 200, r.get_json()
    stripe.finish_onboarding()
    r = client.post(f"{BASE}/refresh")
    assert r.status_code == 200
    return r.get_json()


def test_not_ready_without_an_account(client, club):
    _login(client, "mia@test.ch")
    st = client.get(f"{BASE}/status").get_json()
    assert st["platform"] is True and st["ready"] is False and st["testMode"] is True
    assert "account" not in st
    r = client.post(f"{BASE}/invoices/{club['invoice']}/checkout")
    assert r.status_code == 409 and r.get_json()["error"] == "PAYMENTS_NOT_READY"


def test_connect_then_refresh(client, club, stripe):
    _login(client, "tina@test.ch")
    r = client.post(f"{BASE}/connect")
    assert r.get_json()["url"].startswith("https://connect.stripe.com/")
    created = stripe.calls[0]
    assert created["path"] == "/v1/accounts"
    assert created["form"]["type"] == "standard"
    assert created["form"]["country"] == "CH"
    assert created["headers"]["Authorization"] == "Bearer sk_test_abcdefghijklmnop"
    link = stripe.calls[1]["form"]
    assert link["account"] == "acct_club"
    assert link["return_url"].endswith("/app/payments?connected=1")

    st = client.get(f"{BASE}/status").get_json()
    assert st["account"]["chargesEnabled"] is False and st["ready"] is False

    # A second click opens the same account's setup again.
    client.post(f"{BASE}/connect")
    assert [c["path"] for c in stripe.calls].count("/v1/accounts") == 1

    stripe.finish_onboarding()
    acc = client.post(f"{BASE}/refresh").get_json()["account"]
    assert acc["chargesEnabled"] and acc["twint"] and acc["card"]
    assert acc["name"] == "FC Test"


def test_members_cannot_connect(client, club):
    _login(client, "mia@test.ch")
    assert client.post(f"{BASE}/connect").status_code == 403
    assert client.get(f"{BASE}/checkouts").status_code == 403


def test_pay_an_invoice(client, club, stripe, db):
    from hubra.core.models.finance import Invoice

    _connect(client, stripe)
    _login(client, "mia@test.ch")
    assert client.get(f"{BASE}/status").get_json()["ready"] is True
    r = client.post(f"{BASE}/invoices/{club['invoice']}/checkout")
    assert r.status_code == 200
    assert r.get_json()["url"].startswith("https://checkout.stripe.com/")

    call = stripe.calls[-1]
    assert call["headers"]["Stripe-Account"] == "acct_club"
    form = call["form"]
    assert form["line_items[0][price_data][unit_amount]"] == "12000"
    assert form["line_items[0][price_data][currency]"] == "chf"
    # 1.5 % of CHF 120 for the platform.
    assert form["payment_intent_data[application_fee_amount]"] == "180"
    assert form["metadata[hubra_invoice]"] == str(club["invoice"])
    assert "payment_method_types[0]" not in form
    assert "{CHECKOUT_SESSION_ID}" in form["success_url"]

    # Clicking again while it's open reuses the same checkout.
    again = client.post(f"{BASE}/invoices/{club['invoice']}/checkout").get_json()
    assert again["url"] == r.get_json()["url"]
    assert len(stripe.sessions) == 1

    # Back from Stripe before paying: still open.
    sid = "cs_test_1"
    ok = client.post(f"{BASE}/checkouts/confirm", json={"sessionId": sid}).get_json()
    assert ok["status"] == "open"
    assert db.session.get(Invoice, club["invoice"]).status == "Open"

    stripe.pay(sid)
    ok = client.post(f"{BASE}/checkouts/confirm", json={"sessionId": sid}).get_json()
    assert ok["status"] == "paid" and ok["invoiceId"] == club["invoice"]
    db.session.expire_all()
    assert db.session.get(Invoice, club["invoice"]).status == "Paid"

    r = client.post(f"{BASE}/invoices/{club['invoice']}/checkout")
    assert r.status_code == 409 and r.get_json()["error"] == "INVOICE_PAID"

    _login(client, "tina@test.ch")
    rows = client.get(f"{BASE}/checkouts").get_json()
    assert rows[0]["status"] == "paid" and rows[0]["method"] == "twint"
    assert rows[0]["memberName"] == "Test Mia" and rows[0]["fee"] == 1.8


def test_only_the_invoiced_member_pays(client, club, stripe):
    _connect(client, stripe)
    _login(client, "otto@test.ch")
    r = client.post(f"{BASE}/invoices/{club['invoice']}/checkout")
    assert r.status_code == 404
    _login(client, "mia@test.ch")
    client.post(f"{BASE}/invoices/{club['invoice']}/checkout")
    _login(client, "otto@test.ch")
    r = client.post(f"{BASE}/checkouts/confirm", json={"sessionId": "cs_test_1"})
    assert r.status_code == 404


def test_a_wrong_amount_is_not_booked(client, club, stripe, db):
    from hubra.core.models.finance import Invoice

    _connect(client, stripe)
    _login(client, "mia@test.ch")
    client.post(f"{BASE}/invoices/{club['invoice']}/checkout")
    stripe.pay("cs_test_1", amount=100)
    ok = client.post(f"{BASE}/checkouts/confirm", json={"sessionId": "cs_test_1"})
    assert ok.get_json()["status"] == "open"
    assert db.session.get(Invoice, club["invoice"]).status == "Open"


def test_the_job_books_payments_and_ends_old_checkouts(client, club, stripe, db):
    from hubra.core.models.finance import Invoice
    from hubra_payments import services
    from hubra_payments.models import PaymentCheckout

    _connect(client, stripe)
    _login(client, "mia@test.ch")
    client.post(f"{BASE}/invoices/{club['invoice']}/checkout")
    stripe.pay("cs_test_1", method="card")
    stale = PaymentCheckout(
        invoice_id=club["invoice"],
        member_id=club["mia"],
        stripe_account_id="acct_club",
        session_id="cs_test_gone",
        amount=Decimal("120.00"),
        fee=Decimal("0"),
        currency="chf",
        status="open",
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    db.session.add(stale)
    db.session.commit()

    done = services.sync_open()
    assert done["paid"] == 1 and done["checked"] == 2
    db.session.expire_all()
    assert db.session.get(Invoice, club["invoice"]).status == "Paid"
    assert db.session.get(PaymentCheckout, stale.id).status == "expired"


def test_a_changed_amount_gets_a_new_checkout(client, club, stripe, db):
    from hubra.core.models.finance import Invoice

    _connect(client, stripe)
    _login(client, "mia@test.ch")
    client.post(f"{BASE}/invoices/{club['invoice']}/checkout")
    inv = db.session.get(Invoice, club["invoice"])
    inv.amount = Decimal("80.00")
    db.session.commit()
    client.post(f"{BASE}/invoices/{club['invoice']}/checkout")
    assert len(stripe.sessions) == 2
    assert stripe.calls[-1]["form"]["line_items[0][price_data][unit_amount]"] == "8000"


def test_disconnect_ends_open_checkouts(client, club, stripe):
    _connect(client, stripe)
    _login(client, "mia@test.ch")
    client.post(f"{BASE}/invoices/{club['invoice']}/checkout")
    _login(client, "tina@test.ch")
    assert client.delete(f"{BASE}/connect").status_code == 204
    assert stripe.sessions["cs_test_1"]["status"] == "expired"
    st = client.get(f"{BASE}/status").get_json()
    assert st["account"] is None and st["ready"] is False


def test_no_platform_key(client, club, db):
    from hubra.core.services import platform_settings

    platform_settings.set_many({"payments.stripe.secret_key": None})
    db.session.commit()
    _login(client, "tina@test.ch")
    st = client.get(f"{BASE}/status").get_json()
    assert st["platform"] is False and st["ready"] is False
    r = client.post(f"{BASE}/connect")
    assert r.status_code == 409 and r.get_json()["error"] == "PAYMENTS_NOT_SET_UP"


def test_stripe_errors_reach_the_admin(client, club, stripe, monkeypatch):
    from hubra_payments import stripe_api

    monkeypatch.setattr(
        stripe_api,
        "_send",
        lambda *a: (400, b'{"error": {"message": "Connect is not enabled"}}'),
    )
    _login(client, "tina@test.ch")
    r = client.post(f"{BASE}/connect")
    assert r.status_code == 502
    assert r.get_json()["message"] == "Connect is not enabled"
    assert client.get(f"{BASE}/status").get_json()["account"] is None


def test_module_off_hides_the_api(client, auth_headers):
    set_modules(False, "payments")
    r = client.get(f"{BASE}/status")
    assert r.status_code == 403 and r.get_json()["error"] == "MODULE_DISABLED"


def test_the_plugin_loads_within_its_limits(app):
    from hubra.core.plugins import loader

    with app.app_context():
        spec = loader.current().get("payments")
    assert spec is not None and spec.loaded, spec and spec.error
    assert spec.manifest.get("uses") is not None
