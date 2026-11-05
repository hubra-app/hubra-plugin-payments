"""payments_account and payments_checkouts

Runs in public and in every club's schema, tracked in its own version table
(alembic_version_payments). has_table() keeps it safe to run twice.

Revision ID: 3b8f6d2a9c41
Revises:
Create Date: 2026-11-05 12:00:00

"""

from alembic import op
import sqlalchemy as sa

from hubra.core.plugins.ops import has_table

revision = "3b8f6d2a9c41"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    if not has_table("payments_account"):
        op.create_table(
            "payments_account",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("stripe_account_id", sa.String(64), nullable=False),
            sa.Column("livemode", sa.Boolean(), nullable=False),
            sa.Column("details_submitted", sa.Boolean(), nullable=True),
            sa.Column("charges_enabled", sa.Boolean(), nullable=True),
            sa.Column("card", sa.Boolean(), nullable=True),
            sa.Column("twint", sa.Boolean(), nullable=True),
            sa.Column("display_name", sa.String(200), nullable=True),
            sa.Column("connected_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["connected_by"], ["members.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    if not has_table("payments_checkouts"):
        op.create_table(
            "payments_checkouts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("invoice_id", sa.Integer(), nullable=True),
            sa.Column("member_id", sa.Integer(), nullable=True),
            sa.Column("stripe_account_id", sa.String(64), nullable=False),
            sa.Column("session_id", sa.String(255), nullable=False),
            sa.Column("url", sa.Text(), nullable=True),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("fee", sa.Numeric(12, 2), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("method", sa.String(32), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["invoice_id"], ["invoices.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id"),
        )
        op.create_index(
            "ix_payments_checkouts_invoice_id", "payments_checkouts", ["invoice_id"]
        )


def downgrade():
    op.drop_table("payments_checkouts")
    op.drop_table("payments_account")
