"""subscriptions provider fields

Revision ID: 0002_subscriptions_provider_fields
Revises: 0001_init
Create Date: 2026-01-31
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_subscriptions_provider_fields"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.add_column(sa.Column("provider", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("provider_customer_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("provider_subscription_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("provider_order_id", sa.String(), nullable=True))

        batch_op.create_index("ix_subscriptions_provider", ["provider"])
        batch_op.create_index("ix_subscriptions_provider_customer_id", ["provider_customer_id"])
        batch_op.create_index("ix_subscriptions_provider_subscription_id", ["provider_subscription_id"])
        batch_op.create_index("ix_subscriptions_provider_order_id", ["provider_order_id"])


def downgrade() -> None:
    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.drop_index("ix_subscriptions_provider_order_id")
        batch_op.drop_index("ix_subscriptions_provider_subscription_id")
        batch_op.drop_index("ix_subscriptions_provider_customer_id")
        batch_op.drop_index("ix_subscriptions_provider")

        batch_op.drop_column("provider_order_id")
        batch_op.drop_column("provider_subscription_id")
        batch_op.drop_column("provider_customer_id")
        batch_op.drop_column("provider")

