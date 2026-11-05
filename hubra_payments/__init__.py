"""Online payments: members pay their invoices by card or TWINT.

The club connects its own Stripe account to the platform's (Stripe Connect,
a Standard account). A member who pays an open invoice is sent to a Stripe
Checkout page of the club's account; the money goes to the club, Stripe
takes its fees from it and the platform, if manage › Payments sets a fee,
its share. When Stripe reports the payment as paid, the invoice is marked
paid like a bank payment would (its income transaction is completed).

Stripe can't send Connect webhooks to one club, so Hubra asks: when the
member comes back from Checkout, and every ten minutes for open checkouts.

Permissions:
    payments.account.manage   connect Stripe and see the club's online payments
"""

from hubra.core.modules import Blueprint, Module, NavItem, Schedule

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
    nav=(
        NavItem(
            "/app/payments",
            "shell.nav.payments",
            "credit-card",
            section="more",
            order=60,
            perms=("payments.account.manage",),
        ),
    ),
    tables=("payments_account", "payments_checkouts"),
    tasks=("hubra_payments.tasks",),
    schedule=(
        Schedule("payments-sync-10min", "hubra_payments.tasks.sync_open", 600.0),
    ),
)
