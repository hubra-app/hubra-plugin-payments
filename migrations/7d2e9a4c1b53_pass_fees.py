"""Pass the fees on to members: account settings and the checkout's surcharge

Revision ID: 7d2e9a4c1b53
Revises: 3b8f6d2a9c41
Create Date: 2026-11-06 15:00:00

"""

from alembic import op
import sqlalchemy as sa

from hubra.core.plugins.ops import columns

revision = "7d2e9a4c1b53"
down_revision = "3b8f6d2a9c41"
branch_labels = None
depends_on = None


def upgrade():
    have = columns("payments_account")
    if "pass_fees" not in have:
        op.add_column(
            "payments_account",
            sa.Column(
                "pass_fees", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
        )
    if "surcharge_percent" not in have:
        op.add_column(
            "payments_account",
            sa.Column(
                "surcharge_percent",
                sa.Numeric(5, 2),
                nullable=False,
                server_default="0",
            ),
        )
    if "surcharge_fixed" not in have:
        op.add_column(
            "payments_account",
            sa.Column(
                "surcharge_fixed", sa.Numeric(8, 2), nullable=False, server_default="0"
            ),
        )
    if "surcharge" not in columns("payments_checkouts"):
        op.add_column(
            "payments_checkouts",
            sa.Column(
                "surcharge", sa.Numeric(12, 2), nullable=False, server_default="0"
            ),
        )


def downgrade():
    op.drop_column("payments_checkouts", "surcharge")
    op.drop_column("payments_account", "surcharge_fixed")
    op.drop_column("payments_account", "surcharge_percent")
    op.drop_column("payments_account", "pass_fees")
