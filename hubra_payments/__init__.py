"""Online payments: members pay their invoices by card or TWINT.

The club connects its own Stripe account to the platform's (Stripe Connect,
a Standard account). A member who pays an open invoice is sent to a Stripe
Checkout page of the club's account; the money goes to the club, Stripe
takes its fees from it and Hubra, if manage › Payments sets a Hubra fee,
its share. The club can pass both on to members as a surcharge. When Stripe reports the payment as paid, the invoice is marked
paid like a bank payment would (its income transaction is completed).

Stripe can't send Connect webhooks to one club, so Hubra asks: when the
member comes back from Checkout, and every ten minutes for open checkouts.

Permissions:
    payments.account.manage   connect Stripe and see the club's online payments
"""

from hubra.core.modules import Blueprint, Module, Schedule

module = Module(
    code="payments",
    name="Online payments",
    description="Members pay invoices online by card or TWINT (Stripe)",
    default_enabled=False,
    depends_on=("members", "finance"),
    blueprints=(
        Blueprint(
            "hubra_payments.routes",
            "payments_bp",
            "/api/v1/app/payments",
        ),
    ),
    # No nav entry: the payments are a sub-tab of Finanzen › Buchungen and the
    # Stripe set-up one of Finanzen › Einstellungen
    # (frontend/src/index.tsx), next to Bank & QR-Rechnung.
    tables=("payments_account", "payments_checkouts"),
    tasks=("hubra_payments.tasks",),
    schedule=(
        Schedule("payments-sync-10min", "hubra_payments.tasks.sync_open", 600.0),
    ),
    # Hubra's features it uses, through contracts (docs/contracts.md in hubra).
    consumes={
        "finance.invoice.set_status": ">=1,<2",
    },
)
